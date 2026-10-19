"""Archetype detection: every dimension is multi-valued, combinations get names, rules are validated."""

from __future__ import annotations

import copy
import re
import time

import pytest

from azdo_analyzer.analyze.archetype import (
    ArchetypeRulesError,
    FileIndex,
    compile_archetypes,
    profile_repo,
)
from azdo_analyzer.model import Job, Pipeline, ResourceRef, Stage, Step

NG_PACKAGE = '{"dependencies": {"@angular/core": "^17.3.0", "rxjs": "~7.8.0"}, "devDependencies": {"karma": "~6.4.0"}}'
NG_WORKSPACE = '{"projects": {"web": {"architect": {"test": {"builder": "@angular-devkit/build-angular:karma"}}}}}'
CORE_WEB = '<Project Sdk="Microsoft.NET.Sdk.Web"><PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup></Project>'


def task(name: str, **inputs: str) -> Step:
    return Step(name=name, kind="task", task=name if "@" in name else f"{name}@1", inputs=dict(inputs))


def script(text: str) -> Step:
    return Step(name="script", kind="script", task="script", script=text)


def pipeline(*steps: Step, name: str = "ci", kind: str = "yaml", job_kind: str = "agent", connections: tuple[str, ...] = ()) -> Pipeline:
    p = Pipeline(key=f"build:P:{name}", kind=kind, id=1, name=name, project="P",
                 stages=[Stage(name="s", jobs=[Job(name="j", kind=job_kind, steps=list(steps))])])
    p.resources = [ResourceRef(kind="service_connection", name=c, id=c) for c in connections]
    return p


def classify(rules, files: dict[str, str] | None = None, *pipelines: Pipeline, endpoint_types: dict[str, str] | None = None):
    files = files or {}
    return profile_repo(list(files), files.get, list(pipelines), endpoint_types or {}, rules)


# ---------------------------------------------------------------------------------------------- stacks and combinations
def test_angular_app_with_dockerfile(rules):
    prof = classify(rules, {"package.json": NG_PACKAGE, "angular.json": NG_WORKSPACE, "package-lock.json": "{}", "Dockerfile": "FROM nginx"})
    assert prof.stacks == ["angular"]  # node is replaced by the framework
    assert prof.build_tools == ["npm"] and prof.quality_tools == ["karma"] and prof.artifacts == ["image"]
    assert prof.key == "angular | npm | none | image"
    assert prof.names == ["Angular SPA -> container (nginx)"] and prof.templates == ["angular-container"]
    assert prof.evidence["stacks:angular"] == ["angular.json"]


def test_build_tool_is_assumed_from_the_stack_when_nothing_builds_it(rules):
    prof = classify(rules, {"package.json": NG_PACKAGE})
    assert prof.build_tools == ["npm"]
    assert prof.evidence["build_tools:npm"] == ["assumed for stack angular: no build step for it found"]
    assert classify(rules, {"package.json": NG_PACKAGE, "yarn.lock": ""}).build_tools == ["yarn"]


def test_aspnet_core_with_angular_client_app(rules):
    files = {"MyApp/MyApp.csproj": CORE_WEB, "MyApp/ClientApp/package.json": NG_PACKAGE, "MyApp/ClientApp/angular.json": NG_WORKSPACE,
             "MyApp/ClientApp/package-lock.json": "{}"}
    p = pipeline(task("DotNetCoreCLI@2", command="publish"), task("AzureRmWebAppDeployment@4", WebAppName="shop"))
    prof = classify(rules, files, p)
    assert prof.stacks == ["dotnet", "angular"]
    assert prof.build_tools == ["dotnet", "npm"]
    assert prof.deploy_targets == ["azure-app-service"] and "aspnet-web" in prof.markers
    assert prof.key == "dotnet, angular | dotnet, npm | azure-app-service | none"
    assert prof.names == ["ASP.NET Core + Angular"] and prof.templates == ["dotnet-angular"]


def test_java_maven_with_angular_front_end_to_openshift(rules):
    files = {"pom.xml": "<project><parent><artifactId>spring-boot-starter-parent</artifactId></parent></project>",
             "frontend/package.json": NG_PACKAGE, "frontend/angular.json": "{}", "Dockerfile": "FROM eclipse-temurin:17"}
    p = pipeline(task("Maven@3", goals="clean package"), task("Docker@2", command="buildAndPush"), script("oc apply -f openshift/"))
    prof = classify(rules, files, p)
    assert prof.stacks == ["java-maven", "angular"]
    assert prof.build_tools == ["maven", "npm", "docker"]
    assert prof.deploy_targets == ["openshift"] and prof.artifacts == ["image"]
    assert {"spring-boot", "docker"} <= set(prof.markers)
    assert prof.names == ["Java/Maven + Angular"]


def test_without_a_combination_entry_each_stack_gets_its_own_name(rules):
    ar = copy.deepcopy(rules.archetypes)
    ar["named"] = [e for e in ar["named"] if not isinstance(e["stack"], list)]
    lean = copy.copy(rules)
    lean.archetype_rules = compile_archetypes(ar)
    files = {"pom.xml": "<project/>", "web/package.json": NG_PACKAGE, "Dockerfile": "FROM x"}
    p = pipeline(task("Maven@3"), task("Docker@2", command="buildAndPush"), task("KubernetesManifest@1", action="deploy"))
    prof = classify(lean, files, p)
    assert prof.names == ["Java/Maven -> container -> Kubernetes", "Angular SPA -> container -> Kubernetes"]
    assert prof.templates == ["java-maven-k8s", "angular-k8s"]


@pytest.mark.parametrize(("tfm", "stacks", "windows"), [
    ("<TargetFrameworkVersion>v4.7.2</TargetFrameworkVersion>", ["dotnet-framework"], True),
    ("<TargetFramework>net48</TargetFramework>", ["dotnet-framework"], True),
    ("<TargetFrameworks>net48;net8.0</TargetFrameworks>", ["dotnet-framework", "dotnet"], True),
    ("<TargetFramework>net10.0</TargetFramework>", ["dotnet"], False),
    ("<TargetFramework>netstandard2.0</TargetFramework>", ["dotnet"], False),
    ("<TargetFramework>net8.0-windows</TargetFramework><UseWPF>true</UseWPF>", ["dotnet", "dotnet-desktop"], True),
    ("<TargetFramework>$(AppTargetFramework)</TargetFramework>", ["dotnet-project"], False),
])
def test_dotnet_target_frameworks(rules, tfm, stacks, windows):
    prof = classify(rules, {"src/App/App.csproj": f"<Project><PropertyGroup>{tfm}</PropertyGroup></Project>"})
    assert (prof.stacks, prof.windows) == (stacks, windows)


def test_multi_targeting_gets_a_name_per_stack_and_desktop_covers_dotnet(rules):
    both = classify(rules, {"Lib.csproj": "<TargetFrameworks>net48;net8.0</TargetFrameworks>"})
    assert both.names == [".NET Framework build (Windows)", ".NET build"]
    wpf = classify(rules, {"App.csproj": "<TargetFramework>net8.0-windows</TargetFramework><UseWPF>true</UseWPF>"})
    assert wpf.names == ["WPF / WinForms desktop app (Windows)"]  # also_covers: dotnet


def test_framework_replacements(rules):
    assert classify(rules, {"package.json": '{"dependencies": {"next": "14", "react": "18"}}'}).stacks == ["nextjs"]
    assert classify(rules, {"package.json": '{"dependencies": {"react": "18"}}'}).stacks == ["react"]
    assert classify(rules, {"package.json": '{"dependencies": {"nuxt": "3", "vue": "3"}}'}).stacks == ["nuxt"]
    assert classify(rules, {"bower.json": '{"dependencies": {"angular": "1.8.2"}}'}).stacks == ["angularjs"]
    assert classify(rules, {"package.json": '{"dependencies": {"express": "4"}}'}).stacks == ["node"]


def test_react_native_app_covers_its_platform_folders(rules):
    files = {"package.json": '{"dependencies": {"react-native": "0.74", "react": "18"}}',
             "android/app/src/main/AndroidManifest.xml": "<manifest/>", "android/build.gradle": "apply plugin: 'com.android.application'",
             "ios/App.xcodeproj/project.pbxproj": "", "ios/Podfile": ""}
    prof = classify(rules, files)
    assert prof.stacks == ["react-native", "android", "ios"]  # android replaces java-gradle
    assert prof.macos and not prof.windows
    assert prof.names == ["React Native app"]


def test_fallback_stacks_only_when_nothing_else_is_found(rules):
    assert classify(rules, {"Dockerfile": "FROM x"}).names == ["Container image (Dockerfile only)"]
    assert classify(rules, {"Dockerfile": "FROM x"}).build_tools == ["docker"]
    assert classify(rules, {"charts/a/Chart.yaml": "name: a"}).stacks == ["helm-charts"]
    assert classify(rules, {"deploy.sh": "echo", "db/001.sql": "select 1"}).stacks == ["sql-scripts", "scripts"]
    assert classify(rules, {"go.mod": "module x", "Dockerfile": "FROM x"}).stacks == ["go"]
    unknown = classify(rules, {"README.md": "# hi"})
    assert (unknown.stack, unknown.name, unknown.template) == ("unknown", "custom", None)


def test_vendor_folders_are_ignored_and_names_are_case_insensitive(rules):
    files = {"package.json": "{}", "node_modules/react/package.json": '{"name": "react", "dependencies": {"react": "1"}}',
             "dockerfile": "FROM node"}
    prof = classify(rules, files)
    assert prof.stacks == ["node"] and prof.markers == ["docker"]


def test_inventory_mode_infers_the_stack_from_build_tools(rules):
    prof = classify(rules, {}, pipeline(task("VSBuild@1", solution="**/*.sln"), task("VSTest@2", testSelector="testAssemblies")))
    assert (prof.stacks, prof.build_tools, prof.quality_tools, prof.source) == (["dotnet-framework"], ["msbuild"], ["vstest"], "pipelines")
    assert prof.windows and prof.evidence["stacks:dotnet-framework"] == ["inferred from build tool msbuild"]


def test_python_frameworks_are_markers(rules):
    prof = classify(rules, {"requirements.txt": "Django==4.2\npsycopg2", "manage.py": "import django"})
    assert prof.stacks == ["python"] and "django" in prof.markers and prof.build_tools == ["pip"]


def test_windows_only_platform_stacks(rules):
    prof = classify(rules, {"etl/Load.dtproj": "<Project/>", "reports/Sales.rptproj": "<Project/>"})
    assert prof.stacks == ["ssis", "ssrs"] and prof.windows
    assert prof.names == ["SSIS packages (Windows)", "SSRS reports (Windows)"]


# ------------------------------------------------------------------------------------------------------ pipeline signals
def test_commands_allow_flags_and_paths_but_ignore_echo_and_comments(rules):
    p = pipeline(script("set -e\nkubectl -n prod apply -f k8s/\n./mvnw -B clean deploy\necho make sure\n# helm upgrade app ./chart"))
    prof = classify(rules, {}, p)
    assert prof.deploy_targets == ["kubernetes"]
    assert prof.evidence["deploy_targets:kubernetes"] == ["'kubectl -n prod apply -f k8s/' in pipeline ci"]
    assert "maven" in prof.build_tools and prof.artifacts == ["maven-package"]
    assert "make" not in prof.build_tools and "helm" not in prof.build_tools


@pytest.mark.parametrize(("command", "build", "deploy", "artifacts"), [
    ("upgrade", [], ["kubernetes"], []),
    ("package", ["helm"], [], ["helm-chart"]),
    ("login", [], [], []),
])
def test_helm_task_inputs(rules, command, build, deploy, artifacts):
    prof = classify(rules, {}, pipeline(task("HelmDeploy@0", command=command)))
    assert (prof.build_tools, prof.deploy_targets, prof.artifacts) == (build, deploy, artifacts)


def test_docker_task_default_command_builds_an_image(rules):
    assert classify(rules, {}, pipeline(task("Docker@2", repository="app"))).artifacts == ["image"]
    assert classify(rules, {}, pipeline(task("Docker@2", command="login"))).artifacts == []


def test_specific_azure_targets_replace_the_generic_one(rules):
    deploy = pipeline(task("AzureCLI@2", inlineScript="az webapp deploy --name shop --src-path app.zip"))
    assert classify(rules, {}, deploy).deploy_targets == ["azure-app-service"]
    keyvault = pipeline(task("AzureCLI@2", inlineScript="az keyvault secret show --name x"))
    assert classify(rules, {}, keyvault).deploy_targets == ["azure"]


def test_terraform_deploys_only_when_it_applies(rules):
    plan = classify(rules, {"main.tf": ""}, pipeline(task("TerraformTaskV4@4", command="plan")))
    assert (plan.build_tools, plan.deploy_targets) == (["terraform"], [])
    apply = classify(rules, {"main.tf": ""}, pipeline(task("TerraformTaskV4@4", command="apply")))
    assert apply.deploy_targets == ["terraform"] and apply.names == ["Terraform / IaC"]


def test_on_premises_targets(rules):
    p = pipeline(task("CopyFiles@2", TargetFolder="\\\\fileserver\\drops\\shop"),
                 script("sc.exe stop ShopService\nsc.exe start ShopService"), job_kind="deployment_group")
    prof = classify(rules, {}, p)
    assert prof.deploy_targets == ["windows-service", "deployment-group", "file-share"]


def test_service_connection_types_and_several_artifacts(rules):
    p = pipeline(task("Maven@3", goals="clean deploy"), task("Docker@2", command="push"), task("PublishPipelineArtifact@1"),
                 connections=("sonar-ep",))
    prof = classify(rules, {"pom.xml": "<project/>"}, p, endpoint_types={"sonar-ep": "sonarqube"})
    assert prof.artifacts == ["image", "maven-package", "files"]
    assert prof.quality_tools == ["sonarqube"]
    assert prof.evidence["quality_tools:sonarqube"] == ["sonarqube service connection in pipeline ci"]
    assert prof.names == ["Java/Maven -> container"]  # 2 conditions beat "Java/Maven library (Maven repository)"


def test_repo_scripts_called_by_a_pipeline_are_searched(rules):
    files = {"ci/deploy.sh": "#!/bin/bash\nhelm upgrade --install shop ./chart\n", "ci/unused.sh": "terraform apply"}
    prof = classify(rules, files, pipeline(script("bash ci/deploy.sh")))
    assert prof.deploy_targets == ["kubernetes"]
    assert prof.evidence["deploy_targets:kubernetes"] == ["'helm upgrade --install shop ./chart' in ci/deploy.sh (called by pipeline ci)"]


def test_releases_count_and_deploy_none_condition(rules):
    library = classify(rules, {"pom.xml": "<project/>"}, pipeline(task("Maven@3", goals="package")))
    assert library.names == ["Java/Maven library or app (no deploy)"]
    release = pipeline(task("SSH@0", commands="systemctl restart shop"), name="shop-release", kind="classic_release")
    deployed = classify(rules, {"pom.xml": "<project/>"}, pipeline(task("Maven@3")), release)
    assert deployed.names == ["Java/Maven -> Linux VM (SSH)"]
    assert deployed.evidence["deploy_targets:linux-vm"] == ["task SSH@0 in release shop-release"]


def test_one_name_per_stack_most_specific_first(rules):
    p = pipeline(task("Docker@2", command="buildAndPush"), task("KubernetesManifest@1"), task("oc-cmd@3", cmd="oc rollout latest dc/x"))
    prof = classify(rules, {"pom.xml": "<project/>"}, p)
    assert prof.deploy_targets == ["openshift", "kubernetes"]
    assert prof.names == ["Java/Maven -> container -> OpenShift"]  # same specificity: the first in the list wins


def test_key_order_follows_the_rules_not_the_input(rules):
    files = {"z/package.json": NG_PACKAGE, "a/App.csproj": CORE_WEB}
    assert classify(rules, files).stack == classify(rules, dict(reversed(list(files.items())))).stack == "dotnet, angular"


# ------------------------------------------------------------------------------------------------------- rules file
def test_every_stack_has_a_name_so_every_combination_is_named(rules):
    ar = rules.archetype_rules
    generic = {e.stacks[0] for e in ar.named if e.generic and len(e.stacks) == 1}
    assert set(ar.rules["stacks"]) - generic == set()


@pytest.mark.parametrize(("mutate", "message"), [
    (lambda r: r["stacks"]["node"].update(fils=["package.json"]), "stacks.node: unknown key(s) ['fils']"),
    (lambda r: r["build_tools"]["maven"].update(script_regex="mvn("), "build_tools.maven.script_regex: invalid regex"),
    (lambda r: r["stacks"]["angular"].update(replaces=["nodejs"]), "stacks.angular.replaces: unknown stacks id 'nodejs'"),
    (lambda r: r["named"].append({"name": "X", "stack": "angualr"}), "named[143] (X).stack: unknown stacks id 'angualr'"),
    (lambda r: r["named"].append({"name": "X", "deploy": "iis"}), "named[143] (X): stack is required"),
    (lambda r: r.update(artifact_rules=[]), "unknown section(s) ['artifact_rules']"),
    (lambda r: r.update(stacks=[{"id": "node", "files": ["package.json"]}]), "stacks: expected a mapping of id -> rule"),
])
def test_rule_errors_are_reported_clearly(rules, mutate, message):
    raw = copy.deepcopy(rules.archetypes)
    assert len(raw["named"]) == 143
    mutate(raw)
    with pytest.raises(ArchetypeRulesError, match=re.escape(message)):
        compile_archetypes(raw)


def test_large_repo_listing_is_fast(rules):
    files = [f"src/module{i // 50}/pkg{i % 50}/File{i}.java" for i in range(80_000)]
    files += [f"web/node_modules/lib{i}/package.json" for i in range(5_000)] + ["pom.xml", "web/package.json", "web/angular.json"]
    started = time.perf_counter()
    prof = profile_repo(files, lambda rel: "{}", [], {}, rules)
    assert time.perf_counter() - started < 10
    assert prof.stacks == ["java-maven", "angular"]
    assert len(FileIndex(files).paths) == 80_003
