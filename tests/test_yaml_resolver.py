from __future__ import annotations

from azdo_analyzer.normalize.catalog import TaskCatalog, TaskGroupIndex
from azdo_analyzer.normalize.common import NormContext
from azdo_analyzer.normalize.yaml_pipeline import RepoLoc, YamlResolver, load_yaml, normalize_yaml_pipeline, yaml_triggers


class DictProvider:
    def __init__(self, files: dict[tuple[str, str | None, str], str]):
        self.files = files
        self.requests = []

    def get(self, project, repo, ref, path):
        self.requests.append((repo, ref, path))
        return self.files.get((repo, ref, path))


ROOT = """
resources:
  repositories:
    - repository: tpl
      type: git
      name: Other/templates
      ref: refs/tags/v1
parameters:
  - name: envs
    type: object
    default: [dev, qa]
stages:
  - stage: Build
    jobs:
      - job: b
        steps:
          - template: steps/build.yml
            parameters:
              tool: gradle
          - template: common/lint.yml@tpl
  - ${{ each env in parameters.envs }}:
    - stage: deploy_${{ env }}
      jobs:
        - deployment: d
          environment: app-${{ env }}
          strategy:
            runOnce:
              deploy:
                steps:
                  - script: echo deploy ${{ env }}
              on:
                failure:
                  steps:
                    - script: echo rollback
"""

BUILD = """
parameters:
  - name: tool
    default: maven
  - name: sonar
    type: boolean
    default: false
steps:
  - task: Gradle@3
    inputs:
      tasks: build ${{ parameters.tool }}
  - ${{ if eq(parameters.sonar, true) }}:
    - task: SonarQubePrepare@5
  - ${{ else }}:
    - script: echo no sonar
"""

LINT = """
steps:
  - template: inner.yml
"""

INNER = """
steps:
  - bash: ./lint.sh
"""


def resolver() -> tuple[YamlResolver, DictProvider]:
    provider = DictProvider({
        ("app", None, "azure-pipelines.yml"): ROOT,
        ("app", None, "steps/build.yml"): BUILD,
        ("templates", "refs/tags/v1", "common/lint.yml"): LINT,
        ("templates", "refs/tags/v1", "common/inner.yml"): INNER,
    })
    return YamlResolver(provider, RepoLoc("Proj", "app")), provider


def test_templates_parameters_conditionals_and_each():
    res, provider = resolver()
    doc, body = res.resolve("/azure-pipelines.yml")
    stages = body["stages"]
    assert [s["stage"] for s in stages] == ["Build", "deploy_dev", "deploy_qa"]
    steps = stages[0]["jobs"][0]["steps"]
    assert steps[0] == {"task": "Gradle@3", "inputs": {"tasks": "build gradle"}}
    # both branches of the if/else are kept (union) and the pipeline is flagged dynamic
    assert {"task": "SonarQubePrepare@5"} in steps and {"script": "echo no sonar"} in steps
    assert res.dynamic is True
    # cross-repo template at the pinned ref, with a relative include inside that repo
    assert {"bash": "./lint.sh"} in steps
    assert ("templates", "refs/tags/v1", "common/inner.yml") in provider.requests
    assert stages[2]["jobs"][0]["environment"] == "app-qa"
    assert res.template_aliases == {"tpl"}
    assert res.unresolved == []


def test_unknown_alias_is_reported():
    provider = DictProvider({("app", None, "p.yml"): "steps:\n  - template: x.yml@nope\n"})
    res = YamlResolver(provider, RepoLoc("Proj", "app"))
    _, body = res.resolve("p.yml")
    assert body["steps"] == [{"__unresolved_template__": "x.yml@nope"}]
    assert any("nope" in u for u in res.unresolved)


def test_on_key_is_not_a_boolean():
    data = load_yaml("strategy:\n  runOnce:\n    on:\n      failure: {}\nflag: yes\n")
    assert "on" in data["strategy"]["runOnce"]
    assert data["flag"] == "yes"


def test_yaml_triggers():
    doc = load_yaml("""
trigger:
  batch: true
  branches:
    include: [main, release/*]
    exclude: [release/old]
  paths:
    exclude: [docs]
pr: none
schedules:
  - cron: "0 3 * * *"
    branches:
      include: [main]
    always: true
resources:
  pipelines:
    - pipeline: up
      source: upstream-ci
      project: Other
      trigger: true
""")
    triggers = yaml_triggers(doc, "TfsGit")
    kinds = [t.kind for t in triggers]
    assert kinds == ["ci", "schedule", "pipeline"]
    ci = triggers[0]
    assert ci.branches_include == ["main", "release/*"] and ci.branches_exclude == ["release/old"] and ci.batch
    assert "always" in triggers[1].schedule
    assert triggers[2].source == "upstream-ci" and triggers[2].detail["project"] == "Other"


def test_implicit_ci_trigger_and_pr_ignored_on_azure_repos():
    triggers = yaml_triggers(load_yaml("pr:\n  - main\nsteps: []\n"), "TfsGit")
    assert triggers[0].kind == "ci" and triggers[0].detail.get("implicit")
    assert triggers[1].kind == "pr" and "ignored" in triggers[1].detail


def test_normalize_yaml_pipeline_merges_ui_config():
    provider = DictProvider({("app", None, "azure-pipelines.yml"): "trigger: [main]\nsteps:\n  - task: Maven@3\n  - checkout: self\n    submodules: true\n"})
    ctx = NormContext(project="Proj", project_id="pid", catalog=TaskCatalog([]), task_groups=TaskGroupIndex([]), file_provider=provider)
    definition = {
        "id": 7, "name": "app-ci", "process": {"type": 2, "yamlFilename": "azure-pipelines.yml"},
        "repository": {"id": "r", "name": "app", "type": "TfsGit"},
        "variables": {"TOKEN": {"isSecret": True}},
        "triggers": [{"triggerType": "continuousIntegration", "settingsSourceType": 1, "branchFilters": ["+refs/heads/develop"]}],
    }
    pipeline = normalize_yaml_pipeline(definition, ctx)
    assert pipeline.flags["ui_variables"] == 1
    assert pipeline.flags["ui_trigger_override"] == ["ci"]
    ci = [t for t in pipeline.triggers if t.kind == "ci"]
    assert len(ci) == 1 and ci[0].defined_in == "ui" and ci[0].branches_include == ["develop"]
    assert pipeline.checkout["submodules"] is True
    assert pipeline.task_refs() == ["Maven@3"]
