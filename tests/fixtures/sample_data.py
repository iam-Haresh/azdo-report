"""Sanitized sample data shaped like Azure DevOps Server 2022 REST responses.

`build_sample(out_dir)` writes a raw cache (out/raw/...) and repo clones
(out/repos/...) for a fictional project "Contoso Retail" so the whole
analysis/report pipeline can run offline in tests.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
COLLECTION = "https://azdo.contoso.local/DefaultCollection"
PROJECT = "Contoso Retail"
PID = "6ce954b1-ce1f-45d1-b94d-e6bf2464ba2c"

R_PAY = "a1111111-1111-1111-1111-111111111111"
R_TPL = "a2222222-2222-2222-2222-222222222222"
R_LEG = "a3333333-3333-3333-3333-333333333333"
R_OLD = "a4444444-4444-4444-4444-444444444444"
R_DIS = "a5555555-5555-5555-5555-555555555555"

T = {  # task ids
    "Maven": "ac4ee482-65da-4485-a532-7b085873e532",
    "PublishTestResults": "0b0f01ed-7dde-43ff-9cbb-e48954daf9b1",
    "Docker": "e28912f1-0114-4464-802a-a3a35437fd16",
    "HelmDeploy": "afa7d54d-537b-4dc8-b60a-e0eeea2c9a87",
    "SonarQubePrepare": "15b84ca1-b62f-4a2a-a403-89b77a063157",
    "CmdLine": "d9bafed4-0b18-4f58-968d-86655b4d2ce9",
    "NuGetToolInstaller": "2c65196a-54fd-4a02-9be8-d9d1837b7c5d",
    "NuGetCommand": "333b11bd-d341-40d9-afcf-b32d5ce6f23b",
    "VSBuild": "71a9a2d3-a98a-4caa-96ab-affca411ecda",
    "VSTest": "ef087383-ee5e-42c7-9a53-ab56c98420f9",
    "CopyFiles": "5bfb729a-a7c8-4a78-a7c3-8d717bb7c13c",
    "PublishBuildArtifacts": "2ff763a7-ce83-4e1f-bc89-0ae63477cebe",
    "PowerShell": "e213ff0f-5d5c-4791-802d-52ea3e7be1f1",
    "DownloadSecureFile": "2a6ca863-f2ce-4f4d-8bcb-15e64608ec4b",
    "IISWebAppManagementOnMachineGroup": "1b467810-6725-4b6d-accd-886174c09bba",
    "IISWebAppDeploymentOnMachineGroup": "1b467810-6725-4b6d-accd-886174c09bbb",
    "replacetokens": "a8515ec8-7254-4ffd-912c-86772e2b5962",
    "InvokeRESTAPI": "9c3e8943-130d-4c78-ac63-8af81df62dfb",
    "ManualIntervention": "bcb64569-d51a-4af0-9c01-ea5d05b3b622",
    "WhiteSource": "521d1e15-f5fb-4b73-a93b-b2fe88a9a286",
}
EXT = {"replacetokens": "qetza.replacetokens.replacetokens-task", "SonarQubePrepare": "sonarsource.sonarqube.prepare",
       "WhiteSource": "whitesource.whitesource.task"}
MAJOR = {"Maven": 3, "PublishTestResults": 2, "Docker": 2, "HelmDeploy": 0, "SonarQubePrepare": 5, "CmdLine": 2, "NuGetToolInstaller": 1,
         "NuGetCommand": 2, "VSBuild": 1, "VSTest": 2, "CopyFiles": 2, "PublishBuildArtifacts": 1, "PowerShell": 2, "DownloadSecureFile": 1,
         "IISWebAppManagementOnMachineGroup": 0, "IISWebAppDeploymentOnMachineGroup": 0, "replacetokens": 5, "InvokeRESTAPI": 1,
         "ManualIntervention": 8, "WhiteSource": 21}
TG_PUBLISH = "b1111111-1111-1111-1111-111111111111"
TG_STAMP = "b2222222-2222-2222-2222-222222222222"
SF_SIGNING = "c1111111-1111-1111-1111-111111111111"
EP = {"aks": "e1111111-1111-1111-1111-111111111111", "artifactory": "e2222222-2222-2222-2222-222222222222",
      "sonar": "e3333333-3333-3333-3333-333333333333", "azure": "e4444444-4444-4444-4444-444444444444",
      "snow": "e5555555-5555-5555-5555-555555555555", "ftp": "e6666666-6666-6666-6666-666666666666"}
SECURITY_TEAM = "d1111111-1111-1111-1111-111111111111"


def _task_catalog() -> list[dict]:
    out = []
    for name, tid in T.items():
        entry = {"id": tid, "name": name, "friendlyName": name, "version": {"major": MAJOR[name], "minor": 200, "patch": 0},
                 "execution": {"Node16": {}}, "category": "Build"}
        if name in ("VSBuild", "IISWebAppManagementOnMachineGroup", "IISWebAppDeploymentOnMachineGroup"):
            entry["execution"] = {"PowerShell3": {}}
        if name in EXT:
            entry["contributionIdentifier"] = EXT[name]
        out.append(entry)
    return out


def _step(name: str, display: str, inputs: dict | None = None, **extra) -> dict:
    return {"enabled": True, "continueOnError": False, "alwaysRun": False, "displayName": display, "timeoutInMinutes": 0,
            "condition": "succeeded()", "task": {"id": T[name], "versionSpec": f"{MAJOR[name]}.*", "definitionType": "task"},
            "inputs": inputs or {}, **extra}


def _wf(name: str, display: str, inputs: dict | None = None) -> dict:
    return {"taskId": T[name], "version": f"{MAJOR[name]}.*", "name": display, "refName": "", "enabled": True,
            "definitionType": "task", "inputs": inputs or {}, "environment": {}}


def _repo(rid: str, name: str, branch: str, size: int, **extra) -> dict:
    url = f"{COLLECTION}/Contoso%20Retail/_git/{name.replace(' ', '%20')}"
    return {"id": rid, "name": name, "defaultBranch": f"refs/heads/{branch}", "size": size, "remoteUrl": url, "webUrl": url,
            "project": {"id": PID, "name": PROJECT}, "isDisabled": False, **extra}


PAYMENTS_YAML = """\
trigger:
  branches:
    include: [main]
  paths:
    exclude: [docs/*]
pr:
  branches:
    include: [main]
schedules:
  - cron: "0 2 * * 1-5"
    displayName: nightly
    branches:
      include: [main]
resources:
  repositories:
    - repository: templates
      type: git
      name: Contoso Retail/pipeline-templates
      ref: refs/tags/v2
  pipelines:
    - pipeline: sharedlib
      source: shared-lib-ci
      trigger:
        branches:
          include: [main]
variables:
  - group: payments-common
  - name: imageName
    value: payments-api
parameters:
  - name: deployProd
    type: boolean
    default: false
stages:
  - stage: Build
    jobs:
      - job: build
        pool: Linux-Docker
        steps:
          - template: build/maven.yml@templates
            parameters:
              jdk: '17'
              runSonar: true
          - script: ./scripts/version.sh
            displayName: Compute version
  - stage: Deploy_Dev
    dependsOn: Build
    jobs:
      - deployment: deploy
        pool: Linux-Docker
        environment: payments-dev
        strategy:
          runOnce:
            deploy:
              steps:
                - task: HelmDeploy@0
                  inputs:
                    connectionType: Kubernetes Service Connection
                    kubernetesServiceConnection: aks-internal
                    command: upgrade
                    chartPath: charts/payments
                    releaseName: payments
            on:
              failure:
                steps:
                  - script: echo "rollback"
  - ${{ if eq(parameters.deployProd, true) }}:
    - stage: Deploy_Prod
      dependsOn: Deploy_Dev
      jobs:
        - deployment: deploy
          pool: Linux-Docker
          environment: payments-prod.payments-prod
          strategy:
            runOnce:
              deploy:
                steps:
                  - task: HelmDeploy@0
                    inputs:
                      kubernetesServiceConnection: aks-internal
                      command: upgrade
                      chartPath: charts/payments
"""

MAVEN_TEMPLATE_V2 = """\
parameters:
  - name: jdk
    type: string
    default: '11'
  - name: runSonar
    type: boolean
    default: false
steps:
  - task: Maven@3
    inputs:
      mavenPomFile: pom.xml
      goals: clean package
      jdkVersionOption: '1.${{ parameters.jdk }}'
  - ${{ if eq(parameters.runSonar, true) }}:
    - task: SonarQubePrepare@5
      inputs:
        SonarQube: sonarqube
        scannerMode: Other
  - task: PublishTestResults@2
    inputs:
      testResultsFormat: JUnit
      testResultsFiles: '**/surefire-reports/TEST-*.xml'
  - template: docker.yml
    parameters:
      image: payments
"""

DOCKER_TEMPLATE_V2 = """\
parameters:
  - name: image
    type: string
steps:
  - task: Docker@2
    inputs:
      containerRegistry: artifactory-docker
      repository: ${{ parameters.image }}
      command: buildAndPush
      Dockerfile: Dockerfile
"""

REPO_FILES = {
    "payments-api": {
        "azure-pipelines.yml": PAYMENTS_YAML,
        "scripts/version.sh": (
            "#!/bin/bash\nVERSION=$(git describe --tags --always)\n"
            'echo "##vso[task.setvariable variable=APP_VERSION]$VERSION"\n'
            'echo "##vso[build.updatebuildnumber]$VERSION"\n'
            'curl -s -H "Authorization: Bearer $SYSTEM_ACCESSTOKEN" '
            '"https://azdo.contoso.local/DefaultCollection/Contoso%20Retail/_apis/build/builds/$BUILD_BUILDID/tags/release"\n'
        ),
        "pom.xml": (
            "<project><properties><java.version>17</java.version></properties>\n"
            "<distributionManagement><repository><id>azdo</id>"
            "<url>https://azdo.contoso.local/DefaultCollection/Contoso%20Retail/_packaging/maven-feed/maven/v1</url>"
            "</repository></distributionManagement></project>\n"
        ),
        "settings.xml": "<settings><mirrors><mirror><url>https://artifactory.contoso.local/artifactory/maven-remote</url></mirror></mirrors></settings>\n",
        "Dockerfile": "FROM artifactory.contoso.local/base/eclipse-temurin:17-jre\nCOPY target/app.jar /app.jar\n",
        "charts/payments/Chart.yaml": "apiVersion: v2\nname: payments\nversion: 0.1.0\n",
        "README.md": "# payments-api\n[![Build](https://azdo.contoso.local/DefaultCollection/Contoso%20Retail/_apis/build/status/payments-api-ci?branchName=main)](x)\n",
        ".azuredevops/pull_request_template.md": "## Description\n",
        ".gitattributes": "*.png filter=lfs diff=lfs merge=lfs -text\n",
        "src/main/java/App.java": "class App {}\n",
    },
    "pipeline-templates": {
        "build/maven.yml": MAVEN_TEMPLATE_V2.replace("Maven@3", "Maven@4"),  # default branch differs from tag v2
        "build/docker.yml": DOCKER_TEMPLATE_V2,
    },
    "legacy-web": {
        "LegacyWeb.sln": "Microsoft Visual Studio Solution File, Format Version 12.00\n",
        "LegacyWeb/LegacyWeb.csproj": "<Project><PropertyGroup><TargetFrameworkVersion>v4.8</TargetFrameworkVersion></PropertyGroup></Project>\n",
        "LegacyWeb/Web.config": "<configuration />\n",
        "LegacyWeb/Web.Release.config": "<configuration xmlns:xdt=\"http://schemas.microsoft.com/XML-Document-Transform\" />\n",
        "nuget.config": (
            '<configuration><packageSources><add key="internal" '
            'value="https://azdo.contoso.local/DefaultCollection/_packaging/nuget-internal/nuget/v3/index.json" />'
            "</packageSources></configuration>\n"
        ),
        ".gitmodules": '[submodule "shared"]\n\tpath = shared\n\turl = https://azdo.contoso.local/DefaultCollection/Contoso%20Retail/_git/shared-lib\n',
        "build.ps1": 'Write-Host "##vso[task.logissue type=warning]legacy build"\n',
    },
    "old-tools": {"tools/readme.txt": "old scripts\n"},
}


def raw_files() -> dict[tuple[str, ...], object]:
    builds_def11 = {
        "id": 11, "name": "payments-api-ci", "path": "\\payments", "queueStatus": "enabled", "quality": "definition", "type": "build",
        "process": {"type": 2, "yamlFilename": "/azure-pipelines.yml"},
        "repository": {"id": R_PAY, "name": "payments-api", "type": "TfsGit", "defaultBranch": "refs/heads/main", "clean": "false",
                       "properties": {"fetchDepth": "1"}},
        "queue": {"id": 10, "name": "Linux-Docker", "pool": {"id": 1, "name": "Linux-Docker"}},
        "variables": {"SONAR_TOKEN": {"isSecret": True}, "deployTimeout": {"value": "300", "allowOverride": True}},
        "triggers": [{"triggerType": "continuousIntegration", "settingsSourceType": 2, "branchFilters": [], "pathFilters": [], "batchChanges": False}],
        "_links": {"web": {"href": f"{COLLECTION}/Contoso%20Retail/_build/definition?definitionId=11"}},
        "createdDate": "2024-05-01T10:00:00Z", "authoredBy": {"displayName": "Dana Dev"},
        "latestBuild": {"id": 1104, "finishTime": "2026-09-28T10:20:00Z"},
    }
    builds_def12 = {
        "id": 12, "name": "legacy-web-CI", "path": "\\legacy", "queueStatus": "enabled", "quality": "definition", "type": "build",
        "process": {"type": 1, "phases": [{
            "name": "Agent job 1", "refName": "Job_1", "condition": "succeeded()",
            "target": {"type": 1, "executionOptions": {"type": 0}, "allowScriptsAuthAccessOption": True, "queue": {"id": 11}},
            "steps": [
                _step("NuGetToolInstaller", "Use NuGet"),
                _step("NuGetCommand", "NuGet restore", {"command": "restore", "restoreSolution": "**\\*.sln"}),
                _step("VSBuild", "Build solution", {"solution": "**\\*.sln", "msbuildArgs": "/p:DeployOnBuild=true", "platform": "$(build.platform)",
                                                    "configuration": "$(BuildConfiguration)", "vsVersion": "17.0"}),
                _step("VSTest", "Test assemblies", {"testSelector": "testAssemblies", "testAssemblyVer2": "**\\*test*.dll"}),
                _step("WhiteSource", "WhiteSource scan", {"cwd": "$(System.DefaultWorkingDirectory)"}),
                _step("DownloadSecureFile", "Download signing cert", {"secureFile": SF_SIGNING}),
                {"enabled": True, "displayName": "Task group: Publish web", "inputs": {"ArtifactName": "drop"},
                 "task": {"id": TG_PUBLISH, "versionSpec": "1.*", "definitionType": "metaTask"}},
            ],
        }]},
        "repository": {"id": R_LEG, "name": "legacy-web", "type": "TfsGit", "defaultBranch": "refs/heads/master", "clean": "true",
                       "checkoutSubmodules": False, "properties": {"gitLfsSupport": "false", "fetchDepth": "0"}},
        "queue": {"id": 11, "name": "Windows-VS2022", "pool": {"id": 2, "name": "Windows-VS2022"}},
        "demands": ["msbuild", "visualstudio"],
        "variables": {"BuildConfiguration": {"value": "Release"}, "build.platform": {"value": "Any CPU"},
                      "db-password": {"value": "P@ssw0rd!"}, "ApiKey": {"isSecret": True}},
        "variableGroups": [],
        "triggers": [
            {"triggerType": "continuousIntegration", "branchFilters": ["+refs/heads/master"], "pathFilters": ["+/src", "-/docs"], "batchChanges": True},
            {"triggerType": "schedule", "schedules": [{"branchFilters": ["+refs/heads/master"], "timeZoneId": "W. Europe Standard Time",
                                                       "startHours": 2, "startMinutes": 0, "daysToBuild": 31, "scheduleOnlyWithChanges": True}]},
        ],
        "buildNumberFormat": "$(date:yyyyMMdd)$(rev:.r)", "jobAuthorizationScope": "projectCollection", "jobTimeoutInMinutes": 60,
        "_links": {"web": {"href": f"{COLLECTION}/Contoso%20Retail/_build/definition?definitionId=12"}},
        "latestBuild": {"id": 1201, "finishTime": "2026-09-20T08:00:00Z"},
    }
    builds_def13 = {
        "id": 13, "name": "old-tools-ci", "path": "\\", "queueStatus": "disabled", "type": "build",
        "process": {"type": 1, "phases": [{"name": "Job", "target": {"type": 1, "queue": {"id": 10}},
                                            "steps": [_step("CmdLine", "Run", {"script": "make all"})]}]},
        "repository": {"id": R_OLD, "name": "old-tools", "type": "TfsGit", "defaultBranch": "refs/heads/master"},
        "queue": {"id": 10, "name": "Linux-Docker"},
        "latestBuild": {"id": 900, "finishTime": "2024-03-01T08:00:00Z"},
    }
    builds_def14 = {
        "id": 14, "name": "orphan-ci", "path": "\\", "queueStatus": "enabled", "type": "build",
        "process": {"type": 1, "phases": [{"name": "Job", "target": {"type": 1, "queue": {"id": 10}},
                                            "steps": [_step("CmdLine", "Run", {"script": "echo hi"})]}]},
        "repository": {"id": "a9999999-9999-9999-9999-999999999999", "name": "deleted-repo", "type": "TfsGit"},
        "queue": {"id": 10, "name": "Linux-Docker"},
    }
    build_defs = [builds_def11, builds_def12, builds_def13, builds_def14]

    def run(bid, did, result, branch, start, end, queued=None, reason="individualCI", pool="Linux-Docker", qid=10):
        return {"id": bid, "buildNumber": str(bid), "status": "completed", "result": result, "queueTime": queued or start,
                "startTime": start, "finishTime": end, "reason": reason, "sourceBranch": f"refs/heads/{branch}",
                "definition": {"id": did, "name": "x"}, "queue": {"id": qid, "name": pool, "pool": pool}, "requestedFor": "Dana Dev",
                "repository": {"id": None, "type": "TfsGit"}}

    builds = [
        run(1101, 11, "succeeded", "main", "2026-09-01T10:00:00Z", "2026-09-01T10:12:00Z", "2026-09-01T09:58:00Z"),
        run(1102, 11, "failed", "feature/x", "2026-09-10T11:00:00Z", "2026-09-10T11:05:00Z", reason="pullRequest"),
        run(1103, 11, "succeeded", "main", "2026-09-20T09:00:00Z", "2026-09-20T09:14:00Z", reason="schedule"),
        run(1104, 11, "succeeded", "main", "2026-09-28T10:00:00Z", "2026-09-28T10:20:00Z"),
        run(1201, 12, "succeeded", "master", "2026-09-20T07:30:00Z", "2026-09-20T08:00:00Z", pool="Windows-VS2022", qid=11),
        run(1202, 12, "partiallySucceeded", "master", "2026-09-15T07:30:00Z", "2026-09-15T08:10:00Z", pool="Windows-VS2022", qid=11),
        run(1203, 12, "succeeded", "master", "2026-09-15T07:40:00Z", "2026-09-15T08:05:00Z", pool="Windows-VS2022", qid=11),
    ]

    def rec(name, version, tid=None, rtype="Task", worker="lnx-agent-01"):
        return {"id": name, "parentId": "job", "type": rtype, "name": name, "order": 1, "result": "succeeded",
                "startTime": "2026-09-28T10:01:00Z", "finishTime": "2026-09-28T10:02:00Z", "workerName": worker,
                "task": {"id": tid or T.get(name, "x"), "name": name, "version": version}}

    timeline_1104 = [rec("Checkout", "1.0.0", "6d15af64-176c-496d-b583-fd2ae21d4df4"), rec("Maven", "3.245.0"), rec("SonarQubePrepare", "5.19.0"),
                     rec("PublishTestResults", "2.244.0"), rec("Docker", "2.240.0"), rec("CmdLine", "2.212.0"), rec("HelmDeploy", "0.245.0")]
    timeline_1201 = [rec(n, f"{MAJOR[n]}.1.0", worker="WIN-BUILD-01") for n in ("NuGetToolInstaller", "NuGetCommand", "VSBuild", "VSTest", "WhiteSource",
                                                          "DownloadSecureFile", "CopyFiles", "PublishBuildArtifacts", "PowerShell")]

    def approval(name=None, group=False, auto=False, uname=None):
        if auto:
            return {"rank": 1, "isAutomated": True, "isNotificationOn": False, "id": 0}
        return {"rank": 1, "isAutomated": False, "approver": {"displayName": name, "uniqueName": uname or name, "isContainer": group}}

    iis_deploy = _wf("IISWebAppDeploymentOnMachineGroup", "Deploy IIS website",
                     {"WebSiteName": "$(WebsiteName)", "Package": "$(System.DefaultWorkingDirectory)\\**\\*.zip",
                      "XmlTransformation": "true", "XmlVariableSubstitution": "true"})
    release5 = {
        "id": 5, "name": "legacy-web-release", "path": "\\legacy", "releaseNameFormat": "Release-$(rev:r)",
        "_links": {"web": {"href": f"{COLLECTION}/Contoso%20Retail/_release?definitionId=5"}},
        "createdOn": "2023-01-01T10:00:00Z", "createdBy": {"displayName": "Olly Ops"},
        "artifacts": [{"alias": "_legacy-web-CI", "type": "Build", "isPrimary": True, "definitionReference": {
            "definition": {"id": "12", "name": "legacy-web-CI"}, "project": {"id": PID, "name": PROJECT},
            "defaultVersionType": {"id": "latestType", "name": "Latest"}}}],
        "triggers": [{"triggerType": "artifactSource", "artifactAlias": "_legacy-web-CI",
                      "triggerConditions": [{"sourceBranch": "master", "tags": [], "useBuildDefinitionBranch": False}]}],
        "variables": {"WebsiteName": {"value": "LegacyWeb"}},
        "variableGroups": [2],
        "lastRelease": {"id": 77, "createdOn": "2026-09-21T09:00:00Z"},
        "environments": [
            {"id": 21, "name": "DEV", "rank": 1, "conditions": [{"name": "ReleaseStarted", "conditionType": "event", "value": ""}],
             "preDeployApprovals": {"approvals": [approval(auto=True)], "approvalOptions": {}},
             "postDeployApprovals": {"approvals": [approval(auto=True)], "approvalOptions": {}},
             "deployPhases": [{"rank": 1, "phaseType": "machineGroupBasedDeployment", "name": "Deploy IIS (DEV)",
                               "deploymentInput": {"queueId": 3, "tags": ["web"], "parallelExecution": {"parallelExecutionType": "none"}},
                               "workflowTasks": [
                                   _wf("IISWebAppManagementOnMachineGroup", "Manage IIS website", {"WebsiteName": "$(WebsiteName)"}),
                                   iis_deploy,
                                   _wf("replacetokens", "Replace tokens", {"rootDirectory": "$(System.DefaultWorkingDirectory)", "targetFiles": "**/*.config"}),
                               ]}],
             "variables": {"ConnectionString": {"isSecret": True}},
             "executionPolicy": {"concurrencyCount": 1, "queueDepthCount": 0},
             "retentionPolicy": {"daysToKeep": 30, "releasesToKeep": 3, "retainBuild": True}},
            {"id": 22, "name": "QA", "rank": 2, "conditions": [{"name": "DEV", "conditionType": "environmentState", "value": "4"}],
             "preDeployApprovals": {"approvals": [approval("[Contoso Retail]\\QA Leads", group=True)],
                                    "approvalOptions": {"requiredApproverCount": 1, "releaseCreatorCanBeApprover": True, "timeoutInMinutes": 43200}},
             "postDeployApprovals": {"approvals": [approval(auto=True)], "approvalOptions": {}},
             "preDeploymentGates": {"gatesOptions": {"isEnabled": True, "timeout": 1440, "samplingInterval": 15},
                                    "gates": [{"tasks": [_wf("InvokeRESTAPI", "Check change ticket",
                                                             {"connectedServiceNameSelector": "connectedServiceName",
                                                              "connectedServiceName": EP["snow"], "method": "GET"})]}]},
             "deployPhases": [{"rank": 1, "phaseType": "machineGroupBasedDeployment", "name": "Deploy IIS (QA)",
                               "deploymentInput": {"queueId": 3, "tags": ["web", "qa"]}, "workflowTasks": [iis_deploy]}],
             "executionPolicy": {"concurrencyCount": 1, "queueDepthCount": 1}},
            {"id": 23, "name": "PROD", "rank": 3, "conditions": [{"name": "QA", "conditionType": "environmentState", "value": "4"}],
             "preDeployApprovals": {"approvals": [approval("Alice Admin", uname="CONTOSO\\alice"), approval("Bob Boss", uname="CONTOSO\\bob")],
                                    "approvalOptions": {"requiredApproverCount": 2, "releaseCreatorCanBeApprover": False}},
             "postDeployApprovals": {"approvals": [approval("Ops Team", group=True)], "approvalOptions": {"requiredApproverCount": 1}},
             "deployPhases": [
                 {"rank": 1, "phaseType": "runOnServer", "name": "Agentless job", "deploymentInput": {},
                  "workflowTasks": [_wf("ManualIntervention", "Manual Intervention", {"instructions": "Confirm the deployment window"})]},
                 {"rank": 2, "phaseType": "machineGroupBasedDeployment", "name": "Deploy IIS (PROD)",
                  "deploymentInput": {"queueId": 4, "tags": ["web"]}, "workflowTasks": [iis_deploy]},
             ],
             "executionPolicy": {"concurrencyCount": 1, "queueDepthCount": 0}},
        ],
    }

    def dep(did, env_id, env_name, status, when):
        return {"id": env_id * 1000 + did, "releaseDefinition": {"id": 5, "name": "legacy-web-release"}, "release": {"id": did, "name": f"Release-{did}"},
                "releaseEnvironment": {"id": env_id * 100, "name": env_name}, "definitionEnvironmentId": env_id, "deploymentStatus": status,
                "operationStatus": "Approved", "reason": "automated", "attempt": 1, "queuedOn": when, "startedOn": when, "completedOn": when}

    deployments = [dep(76, 21, "DEV", "succeeded", "2026-09-16T09:00:00Z"), dep(77, 21, "DEV", "succeeded", "2026-09-20T09:00:00Z"),
                   dep(77, 22, "QA", "succeeded", "2026-09-21T09:00:00Z")]

    task_groups = [
        {"id": TG_PUBLISH, "name": "Publish web", "version": {"major": 1, "minor": 0, "patch": 0}, "revision": 3, "definitionType": "metaTask",
         "tasks": [
             _step("CopyFiles", "Copy zip", {"SourceFolder": "$(build.sourcesdirectory)", "Contents": "**/*.zip",
                                             "TargetFolder": "$(build.artifactstagingdirectory)"}),
             _step("PublishBuildArtifacts", "Publish $(ArtifactName)", {"PathtoPublish": "$(build.artifactstagingdirectory)", "ArtifactName": "$(ArtifactName)"}),
             {"enabled": True, "displayName": "Task group: Stamp version", "inputs": {},
              "task": {"id": TG_STAMP, "versionSpec": "1.*", "definitionType": "metaTask"}},
         ]},
        {"id": TG_STAMP, "name": "Stamp version", "version": {"major": 1, "minor": 2, "patch": 0}, "revision": 1, "definitionType": "metaTask",
         "tasks": [_step("PowerShell", "Stamp build number", {"targetType": "inline", "script": (
             'Write-Host "##vso[build.updatebuildnumber]$(Build.BuildNumber)-legacy"\n'
             'Invoke-RestMethod -Uri "https://azdo.contoso.local/DefaultCollection/Contoso%20Retail/_apis/build/builds/$(Build.BuildId)/tags/legacy" '
             '-Headers @{Authorization = "Bearer $env:SYSTEM_ACCESSTOKEN"}')})]},
    ]
    variable_groups = [
        {"id": 1, "name": "payments-common", "type": "Vsts",
         "variables": {"APP_NAME": {"value": "payments"}, "docker.registry": {"value": "artifactory.contoso.local"},
                       "NEXUS_PASSWORD": {"value": "hunter22"}, "DEPLOY_KEY": {"isSecret": True, "value": None}},
         "variableGroupProjectReferences": [{"projectReference": {"name": PROJECT}}, {"projectReference": {"name": "Contoso Shared"}}]},
        {"id": 2, "name": "legacy-kv", "type": "AzureKeyVault", "providerData": {"serviceEndpointId": EP["azure"], "vault": "kv-legacy"},
         "variables": {"SqlPassword": {"isSecret": True, "enabled": True}}},
    ]
    endpoints = [
        {"id": EP["aks"], "name": "aks-internal", "type": "kubernetes", "url": "https://aks-api.contoso.local:6443", "authorization": {"scheme": "Kubernetes"}, "isShared": False, "isReady": True},
        {"id": EP["artifactory"], "name": "artifactory-docker", "type": "dockerregistry", "url": "https://artifactory.contoso.local", "authorization": {"scheme": "UsernamePassword"}, "isShared": False},
        {"id": EP["sonar"], "name": "sonarqube", "type": "sonarqube", "url": "https://sonar.contoso.local", "authorization": {"scheme": "UsernamePassword"}},
        {"id": EP["azure"], "name": "azure-prod", "type": "azurerm", "url": "https://management.azure.com/", "authorization": {"scheme": "ServicePrincipal"}},
        {"id": EP["snow"], "name": "servicenow-generic", "type": "generic", "url": "https://contoso.service-now.com", "authorization": {"scheme": "UsernamePassword"}},
        {"id": EP["ftp"], "name": "old-ftp", "type": "generic", "url": "ftp://ftp.contoso.local", "authorization": {"scheme": "UsernamePassword"},
         "isShared": True, "serviceEndpointProjectReferences": [{"projectReference": {"name": PROJECT}}, {"projectReference": {"name": "Contoso Shared"}}]},
    ]
    policies = [
        {"id": 1, "isEnabled": True, "isBlocking": True, "type": {"displayName": "Minimum number of reviewers"},
         "settings": {"minimumApproverCount": 2, "creatorVoteCounts": False, "resetOnSourcePush": True,
                      "scope": [{"repositoryId": R_PAY, "refName": "refs/heads/main", "matchKind": "Exact"}]}},
        {"id": 2, "isEnabled": True, "isBlocking": True, "type": {"displayName": "Build"},
         "settings": {"buildDefinitionId": 11, "queueOnSourceUpdateOnly": True, "manualQueueOnly": False, "validDuration": 720,
                      "filenamePatterns": ["/src/*"], "scope": [{"repositoryId": R_PAY, "refName": "refs/heads/main", "matchKind": "Exact"}]}},
        {"id": 3, "isEnabled": True, "isBlocking": True, "type": {"displayName": "Required reviewers"},
         "settings": {"requiredReviewerIds": [SECURITY_TEAM], "filenamePatterns": ["/src/security/*"], "minimumApproverCount": 1,
                      "scope": [{"repositoryId": R_PAY, "refName": "refs/heads/main", "matchKind": "Exact"}]}},
        {"id": 4, "isEnabled": True, "isBlocking": True, "type": {"displayName": "Comment requirements"},
         "settings": {"scope": [{"repositoryId": R_PAY, "refName": "refs/heads/main", "matchKind": "Exact"}]}},
        {"id": 5, "isEnabled": True, "isBlocking": True, "type": {"displayName": "Status"},
         "settings": {"statusGenre": "security-scan", "statusName": "checkmarx",
                      "scope": [{"repositoryId": R_PAY, "refName": "refs/heads/main", "matchKind": "Exact"}]}},
        {"id": 6, "isEnabled": True, "isBlocking": True, "type": {"displayName": "Require a merge strategy"},
         "settings": {"allowSquash": True, "allowNoFastForward": False, "scope": [{"repositoryId": R_LEG, "refName": "refs/heads/master", "matchKind": "Exact"}]}},
        {"id": 7, "isEnabled": True, "isBlocking": True, "type": {"displayName": "File size restriction"},
         "settings": {"maximumGitBlobSizeInBytes": 104857600, "scope": [{"repositoryId": None}]}},
    ]

    def branch(name, date, base=False):
        return {"name": name, "isBaseVersion": base, "aheadCount": 0, "behindCount": 0,
                "commit": {"committer": {"date": date}, "author": {"date": date}}}

    files: dict[tuple[str, ...], object] = {
        ("_org", "projects.json"): [{"id": PID, "name": PROJECT, "state": "wellFormed"}],
        ("_org", "project_details", f"{PID}.json"): {"id": PID, "name": PROJECT, "capabilities": {
            "versioncontrol": {"sourceControlType": "Git", "gitEnabled": "True", "tfvcEnabled": "False"}, "processTemplate": {"templateName": "Agile"}}},
        ("_org", "tasks.json"): _task_catalog(),
        ("_org", "extensions.json"): [{"publisherId": "qetza", "extensionId": "replacetokens", "version": "5.3.0"},
                                      {"publisherId": "sonarsource", "extensionId": "sonarqube", "version": "5.19.0"},
                                      {"publisherId": "whitesource", "extensionId": "whitesource", "version": "21.1.0"}],
        ("_org", "pools.json"): [{"id": 1, "name": "Linux-Docker", "isHosted": False}, {"id": 2, "name": "Windows-VS2022", "isHosted": False}],
        ("_org", "agents", "1.json"): [{"name": "lnx-agent-01", "version": "3.236.1", "status": "online", "enabled": True,
                                        "osDescription": "Linux 5.15 Ubuntu 22.04",
                                        "systemCapabilities": {"Agent.OS": "Linux", "java": "/usr/lib/jvm/java-17", "maven": "/usr/share/maven",
                                                               "docker": "/usr/bin/docker", "kubectl": "/usr/local/bin/kubectl", "helm": "/usr/local/bin/helm",
                                                               "node.js": "/usr/bin/node", "git": "/usr/bin/git"},
                                        "lastCompletedRequest": {"finishTime": "2026-09-28T10:20:00Z"}}],
        ("_org", "agents", "2.json"): [{"name": "WIN-BUILD-01", "version": "3.236.1", "status": "online", "enabled": True,
                                        "osDescription": "Microsoft Windows 10.0.20348",
                                        "systemCapabilities": {"Agent.OS": "Windows_NT", "MSBuild_17.0": "C:\\MSBuild", "VisualStudio_17.0": "C:\\VS",
                                                               "VSTest_17.0": "C:\\VSTest", "DotNetFramework_4.8": "C:\\NET", "git": "C:\\git"}}],
        ("_org", "feeds.json"): [{"id": "f1", "name": "nuget-internal", "upstreamSources": [{"name": "nuget.org"}]}],
        ("_org", "hooks.json"): [{"id": "h1", "consumerId": "teams", "eventType": "build.complete", "publisherInputs": {"projectId": PID}},
                                 {"id": "h2", "consumerId": "webHooks", "eventType": "git.push", "publisherInputs": {"projectId": "other"}}],
        ("_org", "_meta.json"): {"fetched_at": "2026-10-01T08:00:00Z", "collection_url": COLLECTION},
        ("_org", "coverage.json"): [{"scope": "_org", "collector": "org", "endpoint": "distributedtask/tasks", "status": "OK", "calls": 1,
                                     "failed": 0, "items": len(T), "message": ""}],
        (PROJECT, "_meta.json"): {"fetched_at": "2026-10-01T08:00:00Z", "depth": "deep", "project_id": PID},
        (PROJECT, "repos.json"): [
            _repo(R_PAY, "payments-api", "main", 5_242_880),
            _repo(R_TPL, "pipeline-templates", "main", 102_400),
            _repo(R_LEG, "legacy-web", "master", 6_442_450_944),
            _repo(R_OLD, "old-tools", "master", 20_480),
            _repo(R_DIS, "Data Scripts", "main", 4_096, isDisabled=True),
        ],
        (PROJECT, "repo", R_PAY, "branch_stats.json"): [branch("main", "2026-09-28T09:00:00Z", True), branch("feature/x", "2026-09-10T09:00:00Z"),
                                                       branch("release/1.0", "2025-01-01T09:00:00Z")],
        (PROJECT, "repo", R_TPL, "branch_stats.json"): [branch("main", "2026-08-15T09:00:00Z", True)],
        (PROJECT, "repo", R_LEG, "branch_stats.json"): [branch("master", "2026-09-19T09:00:00Z", True), branch("develop", "2026-09-25T09:00:00Z"),
                                                       branch("release/2026.09", "2026-09-01T09:00:00Z"), branch("hotfix/login", "2026-09-03T09:00:00Z")],
        (PROJECT, "repo", R_OLD, "branch_stats.json"): [branch("master", "2024-02-01T09:00:00Z", True)],
        (PROJECT, "repo", R_PAY, "tags.json"): [{"name": "refs/tags/v1.0.0"}, {"name": "refs/tags/v1.1.0"}],
        (PROJECT, "repo", R_TPL, "tags.json"): [{"name": "refs/tags/v2"}],
        (PROJECT, "repo", R_PAY, "open_prs.json"): [{"pullRequestId": 7, "creationDate": "2026-09-25T10:00:00Z"}],
        (PROJECT, "repo", R_LEG, "open_prs.json"): [{"pullRequestId": 3, "creationDate": "2026-06-01T10:00:00Z"}],
        (PROJECT, "policy_configurations.json"): policies,
        (PROJECT, "identities.json"): {SECURITY_TEAM: {"displayName": "[Contoso Retail]\\Security Team", "isGroup": True}},
        (PROJECT, "tfvc_changesets.json"): [],
        (PROJECT, "build_definitions.json"): build_defs,
        (PROJECT, "builds.json"): builds,
        (PROJECT, "timeline", "1104.json"): timeline_1104,
        (PROJECT, "timeline", "1201.json"): timeline_1201,
        (PROJECT, "release_definitions.json"): [{"id": 5, "name": "legacy-web-release", "lastRelease": release5["lastRelease"]}],
        (PROJECT, "release_definition", "5.json"): release5,
        (PROJECT, "deployments.json"): deployments,
        (PROJECT, "variable_groups.json"): variable_groups,
        (PROJECT, "secure_files.json"): [{"id": SF_SIGNING, "name": "signing.pfx", "modifiedOn": "2025-01-10T10:00:00Z",
                                          "modifiedBy": {"displayName": "Alice Admin"}}],
        (PROJECT, "task_groups.json"): task_groups,
        (PROJECT, "feeds.json"): [{"id": "f2", "name": "maven-feed"}],
        (PROJECT, "wikis.json"): [{"name": "Contoso-Retail.wiki", "type": "projectWiki"}],
        (PROJECT, "service_endpoints.json"): endpoints,
        (PROJECT, "endpoint_history", f"{EP['aks']}.json"): [{"data": {"definition": {"id": 11, "name": "payments-api-ci"}, "planType": "Build",
                                                                       "result": "succeeded", "finishTime": "2026-09-28T10:19:00Z"}}],
        (PROJECT, "queues.json"): [{"id": 10, "name": "Linux-Docker", "pool": {"id": 1, "name": "Linux-Docker"}},
                                   {"id": 11, "name": "Windows-VS2022", "pool": {"id": 2, "name": "Windows-VS2022"}}],
        (PROJECT, "environments.json"): [{"id": 1, "name": "payments-dev"}, {"id": 2, "name": "payments-prod"}],
        (PROJECT, "environment", "1.json"): {"id": 1, "name": "payments-dev", "resources": [{"id": 1, "name": "payments", "type": "kubernetes", "tags": []}]},
        (PROJECT, "environment", "2.json"): {"id": 2, "name": "payments-prod", "resources": [{"id": 2, "name": "payments-prod", "type": "kubernetes", "tags": ["prod"]}]},
        (PROJECT, "environment_deployments", "1.json"): [{"definition": {"id": 11, "name": "payments-api-ci"}, "stageName": "Deploy_Dev", "jobName": "deploy",
                                                          "result": "succeeded", "startTime": "2026-09-28T10:15:00Z", "finishTime": "2026-09-28T10:19:00Z"}],
        (PROJECT, "environment_deployments", "2.json"): [],
        (PROJECT, "checks", "environment_2.json"): [
            {"type": {"id": "8c6f20a7-a545-4486-9777-f762fafe0d4d", "name": "Approval"},
             "settings": {"approvers": [{"displayName": "[Contoso Retail]\\Prod Approvers", "id": "g-1"}], "minRequiredApprovers": 1}},
            {"type": {"id": "fe1de3ee-a436-41b4-bb20-f6eb4cb879a7", "name": "Task Check"},
             "settings": {"displayName": "Branch control", "definitionRef": {"name": "evaluatebranchProtection"}, "inputs": {"allowedBranches": "refs/heads/main"}}},
            {"type": {"id": "fe1de3ee-a436-41b4-bb20-f6eb4cb879a7", "name": "Task Check"},
             "settings": {"displayName": "Business hours", "definitionRef": {"name": "BusinessHours"}}},
        ],
        (PROJECT, "checks", "environment_1.json"): [],
        (PROJECT, "pipeline_permissions", f"endpoint_{EP['aks']}.json"): {"allPipelines": {"authorized": False}, "pipelines": [{"id": 11, "authorized": True}]},
        (PROJECT, "pipeline_permissions", "variablegroup_1.json"): {"allPipelines": {"authorized": True}, "pipelines": []},
        (PROJECT, "deployment_groups.json"): [
            {"id": 3, "name": "web-dev-servers", "machines": [{"agent": {"name": "WEBDEV01", "osDescription": "Microsoft Windows 10.0.17763"}, "tags": ["web", "qa"]}]},
            {"id": 4, "name": "web-prod-servers", "machines": [{"agent": {"name": "WEBPROD01", "osDescription": "Microsoft Windows 10.0.17763"}, "tags": ["web"]},
                                                               {"agent": {"name": "WEBPROD02", "osDescription": "Microsoft Windows 10.0.17763"}, "tags": ["web"]}]},
        ],
        (PROJECT, "files", "pipeline-templates", "v2", "build", "maven.yml"): {"content": MAVEN_TEMPLATE_V2},
        (PROJECT, "files", "pipeline-templates", "v2", "build", "docker.yml"): {"content": DOCKER_TEMPLATE_V2},
        (PROJECT, "coverage.json"): [
            {"scope": PROJECT, "collector": "resources", "endpoint": "distributedtask/deploymentgroups", "status": "OK", "calls": 1, "failed": 0, "items": 2, "message": ""},
            {"scope": PROJECT, "collector": "connections", "endpoint": "serviceendpoint/{id}/executionhistory", "status": "FORBIDDEN", "calls": 6,
             "failed": 5, "items": 1, "message": "TF400813: not authorized"},
        ],
    }
    for definition in build_defs:  # deep collection stores the full GET of each definition too
        files[(PROJECT, "build_definition", f"{definition['id']}.json")] = definition
    return files


def build_sample(out_dir: Path) -> Path:
    """Write the sample raw cache and repo files under ``out_dir`` (the configured output dir)."""
    raw = out_dir / "raw"
    for parts, data in raw_files().items():
        target = raw.joinpath(*parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, indent=1), encoding="utf-8")
    for repo, files in REPO_FILES.items():
        for rel, content in files.items():
            target = out_dir / "repos" / PROJECT / repo / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
    return out_dir
