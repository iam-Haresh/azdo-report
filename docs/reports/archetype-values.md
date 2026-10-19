# Archetype values

[Report guide](README.md) › Archetype values

Every value the tool can report in the Stack, Build tools, Test & scan tools, Deploy targets, Artifacts and Markers columns,
how each one is found, and the named archetypes with their proposed templates. How the values combine into the archetype
key is explained in [Concepts](concepts.md#archetype-key).

This page is generated from `rules/archetypes.yaml`. After editing the rules, regenerate it with
`python -m azdo_analyzer.report.archetype_doc`.

**Found from** lists the signals. Any one of them is enough:
- *files*: file names anywhere in the repo (deep runs), not case-sensitive. "with content check" means one of those files
  must also contain the regex shown.
- *tasks*, *task inputs*: tasks in the build pipelines and classic releases that use the repo.
- *commands*, *script regex*: inline scripts and task inputs of those pipelines, and repo scripts they call by name.
- *connection type*: a service connection of that type is used. *markers*: a marker below was found.

## Stack

67 values.

| Value | What it is | Found from | Notes |
|---|---|---|---|
| `dotnet-framework` | .NET Framework (Windows) | files `*.csproj`, `*.vbproj`, `*.fsproj`, `Directory.Build.props` with content check `<TargetFramework(?:Version\|s)?>[^<]*\b(?:v[1-4]\.\d\|net[1-4]\d{1,2}(?![\d.]))` | Windows runner; replaces `dotnet-project`; built with msbuild, dotnet, cake, nuke (assumed: msbuild) |
| `dotnet` | .NET (Core, 5 and later) | files `*.csproj`, `*.vbproj`, `*.fsproj`, `Directory.Build.props`, `global.json` with content check `<TargetFrameworks?>[^<]*\b(?:net(?:[5-9]\|\d{2})\.\d\|netcoreapp\d\|netstandard\d)\|"sdk"\s*:` | replaces `dotnet-project`; built with dotnet, msbuild, cake, nuke (assumed: dotnet) |
| `dotnet-desktop` | WPF / WinForms on .NET (Windows) | files `*.csproj`, `*.vbproj`, `Directory.Build.props` with content check `<Use(?:WPF\|WindowsForms)>\s*true\|<TargetFrameworks?>[^<]*\bnet\d+\.\d+-windows` | Windows runner; replaces `dotnet-project`; built with dotnet, msbuild (assumed: dotnet) |
| `windows-app` | UWP / WinUI / MSIX packaged app (Windows) | files `Package.appxmanifest`, `*.wapproj`; files `*.csproj` with content check `<UseWinUI>\s*true\|<TargetPlatformIdentifier>\s*UAP` | Windows runner; replaces `dotnet-project`; built with msbuild (assumed: msbuild) |
| `xamarin` | Xamarin (end of support May 2024; iOS builds need macOS) | files `*.csproj` with content check `Xamarin\.(?:iOS\|Android\|Forms\|Essentials)\|MonoAndroid` | replaces `dotnet-project`; built with msbuild (assumed: msbuild) |
| `maui` | .NET MAUI (iOS and macOS targets need macOS) | files `*.csproj` with content check `<UseMaui>\s*true` | replaces `dotnet-project`; built with dotnet (assumed: dotnet) |
| `dotnet-project` | .NET project (target framework not detected) | files `*.csproj`, `*.vbproj`, `*.fsproj`, `*.sln` | built with dotnet, msbuild (assumed: dotnet) |
| `java-maven` | Java / Maven | files `pom.xml` | built with maven (assumed: maven) |
| `java-gradle` | Java / Kotlin with Gradle | files `build.gradle`, `build.gradle.kts`, `settings.gradle`, `settings.gradle.kts` | built with gradle (assumed: gradle) |
| `java-ant` | Java / Ant | files `build.xml` with content check `<target\b[^>]*\bname=` | built with ant (assumed: ant) |
| `scala-sbt` | Scala / sbt | files `build.sbt` | built with sbt (assumed: sbt) |
| `python` | Python | files `requirements*.txt`, `pyproject.toml`, `setup.py`, `setup.cfg`, `Pipfile`, `environment.yml`, `environment.yaml`, `tox.ini` | built with pip, poetry, pipenv, conda, uv (assumed: pip) |
| `go` | Go | files `go.mod` | built with go (assumed: go) |
| `rust` | Rust | files `Cargo.toml` | built with cargo (assumed: cargo) |
| `php` | PHP | files `composer.json` | built with composer (assumed: composer) |
| `ruby` | Ruby | files `Gemfile` | built with bundler (assumed: bundler) |
| `cpp-msvc` | C / C++ Visual Studio project (Windows) | files `*.vcxproj`, `*.vcproj` | Windows runner; replaces `c-cpp`; built with msbuild (assumed: msbuild) |
| `cpp-cmake` | C / C++ with CMake | files `CMakeLists.txt` | replaces `c-cpp`; built with cmake (assumed: cmake) |
| `c-cpp` | C / C++ | files `*.c`, `*.cpp`, `*.cc`, `*.cxx` | built with make, cmake (assumed: make) |
| `r` | R | files `renv.lock`, `*.Rproj` |  |
| `angular` | Angular | files `angular.json`, `.angular-cli.json`; files `package.json` with content check `"@angular/core"\s*:` | replaces `node`; built with npm, yarn, pnpm, angular-cli (assumed: npm) |
| `angularjs` | AngularJS 1.x (end of life) | files `package.json`, `bower.json` with content check `"angular"\s*:` | replaces `node`; built with npm, yarn, bower, grunt, gulp (assumed: npm) |
| `react` | React | files `package.json` with content check `"react"\s*:` | replaces `node`; built with npm, yarn, pnpm (assumed: npm) |
| `nextjs` | Next.js | files `next.config.js`, `next.config.mjs`, `next.config.ts`; files `package.json` with content check `"next"\s*:` | replaces `react`, `node`; built with npm, yarn, pnpm (assumed: npm) |
| `gatsby` | Gatsby | files `gatsby-config.js`, `gatsby-config.ts`, `gatsby-config.mjs` | replaces `react`, `node`; built with npm, yarn, pnpm (assumed: npm) |
| `react-native` | React Native | files `package.json` with content check `"react-native"\s*:` | replaces `react`, `node`; built with npm, yarn, pnpm (assumed: npm) |
| `vue` | Vue.js | files `vue.config.js`; files `package.json` with content check `"vue"\s*:` | replaces `node`; built with npm, yarn, pnpm (assumed: npm) |
| `nuxt` | Nuxt | files `nuxt.config.js`, `nuxt.config.ts`; files `package.json` with content check `"nuxt"\s*:` | replaces `vue`, `node`; built with npm, yarn, pnpm (assumed: npm) |
| `svelte` | Svelte / SvelteKit | files `svelte.config.js`; files `package.json` with content check `"svelte"\s*:` | replaces `node`; built with npm, yarn, pnpm (assumed: npm) |
| `electron` | Electron desktop app | files `package.json` with content check `"electron"\s*:` | replaces `node`; built with npm, yarn, pnpm (assumed: npm) |
| `hybrid-mobile` | Ionic / Capacitor / Cordova hybrid app | files `ionic.config.json`, `capacitor.config.json`, `capacitor.config.ts`; files `package.json` with content check `"(?:@ionic/(?:angular\|react\|vue)\|@capacitor/core\|cordova-android\|cordova-ios)"\s*:` | replaces `node`; built with npm, yarn, pnpm (assumed: npm) |
| `spfx` | SharePoint Framework (SPFx) | files `config/package-solution.json`; files `package.json` with content check `"@microsoft/sp-` | replaces `node`; built with npm, gulp (assumed: npm) |
| `node` | Node.js / JavaScript (no front-end framework found) | files `package.json` | built with npm, yarn, pnpm (assumed: npm) |
| `android` | Android app (Android SDK) | files `AndroidManifest.xml`; files `build.gradle`, `build.gradle.kts` with content check `com\.android\.(?:application\|library)` | replaces `java-gradle`; built with gradle (assumed: gradle) |
| `ios` | iOS / macOS app (Xcode; needs a macOS runner) | files `*.xcodeproj/project.pbxproj`, `*.xcworkspace/contents.xcworkspacedata`, `Podfile`, `Cartfile` | macOS runner; built with xcodebuild, fastlane (assumed: xcodebuild) |
| `flutter` | Flutter | files `pubspec.yaml` with content check `sdk:\s*flutter` | built with flutter (assumed: flutter) |
| `database` | Database project (SSDT, Flyway, Liquibase) | files `*.sqlproj`, `flyway.conf`, `flyway.toml`, `liquibase.properties`, `db.changelog*.xml`, `db.changelog*.yaml`, `db.changelog*.yml` |  |
| `ssis` | SSIS packages (Windows) | files `*.dtproj` | Windows runner; built with ssis-build, devenv (assumed: ssis-build) |
| `ssrs` | SSRS reports (Windows) | files `*.rptproj` | Windows runner; built with msbuild, devenv (assumed: msbuild) |
| `ssas` | SSAS models (Windows) | files `*.smproj`, `*.dwproj` | Windows runner; built with msbuild, devenv (assumed: msbuild) |
| `power-bi` | Power BI reports | files `*.pbix`, `*.pbip`, `*.pbit` |  |
| `azure-data-factory` | Azure Data Factory | files `ARMTemplateForFactory.json`, `publish_config.json`, `*linkedService/*.json`, `*dataset/*.json`, `*factory/*.json` with content check `Microsoft\.DataFactory\|"typeProperties"\|"publishBranch"` |  |
| `databricks` | Databricks asset bundle | files `databricks.yml`, `databricks.yaml` |  |
| `dbt` | dbt project | files `dbt_project.yml` |  |
| `power-platform` | Power Platform solution / PCF control | files `*.cdsproj`, `*.pcfproj`, `*Other/Solution.xml` |  |
| `salesforce` | Salesforce (SFDX) | files `sfdx-project.json` |  |
| `biztalk` | BizTalk (Windows) | files `*.btproj` | Windows runner; built with msbuild (assumed: msbuild) |
| `delphi` | Delphi (Windows) | files `*.dproj` | Windows runner; built with msbuild (assumed: msbuild) |
| `vb6` | Visual Basic 6 (Windows) | files `*.vbp` | Windows runner |
| `terraform` | Terraform / Terragrunt | files `*.tf`, `terragrunt.hcl` | built with terraform (assumed: terraform) |
| `bicep` | Bicep | files `*.bicep`, `*.bicepparam` |  |
| `arm-templates` | ARM templates | files `azuredeploy*.json`, `mainTemplate.json`, `template.json`, `*.deploymentTemplate.json`, `*.arm.json` with content check `schemas/[^"]*deploymentTemplate\.json` |  |
| `cloudformation` | AWS CloudFormation / SAM | files `*.template`, `*.template.json`, `*.template.yaml`, `*.template.yml`, `*.cfn.json`, `*.cfn.yaml`, `*.cfn.yml`, `template.yaml`, `template.yml`, `*cloudformation*/*.yaml`, `*cloudformation*/*.yml`, `*cloudformation*/*.json` with content check `AWSTemplateFormatVersion\|AWS::\w+::\w+` |  |
| `aws-cdk` | AWS CDK | files `cdk.json` |  |
| `pulumi` | Pulumi | files `Pulumi.yaml`, `Pulumi.yml` |  |
| `ansible` | Ansible | files `ansible.cfg`, `playbook*.yml`, `playbook*.yaml`, `site.yml`, `site.yaml`, `*roles/*/tasks/main.yml`, `*roles/*/tasks/main.yaml` |  |
| `chef` | Chef | files `Berksfile`, `Policyfile.rb`, `*recipes/*.rb` |  |
| `puppet` | Puppet | files `*.pp`, `Puppetfile` |  |
| `packer` | Packer (VM images) | files `*.pkr.hcl`, `*.pkr.json` | built with packer (assumed: packer) |
| `powershell` | PowerShell module | files `*.psd1`, `*.psm1` |  |
| `docs` | Documentation site (MkDocs, DocFX, Sphinx, Hugo, Jekyll, Docusaurus, Antora) | files `mkdocs.yml`, `mkdocs.yaml`, `docfx.json`, `hugo.toml`, `hugo.yaml`, `_config.yml`, `docusaurus.config.js`, `docusaurus.config.ts`, `antora.yml`, `antora-playbook.yml`, `docs/conf.py`, `doc/conf.py`, … (+1) |  |
| `azdo-yaml-templates` | Azure DevOps YAML templates used by other pipelines (set by the tool, no file rule) | set by the tool |  |
| `helm-charts` | Helm charts only | markers `helm` | only when no other stack is found; built with helm (assumed: helm) |
| `kubernetes-manifests` | Kubernetes / OpenShift manifests only | markers `kustomize`, `k8s-manifests`, `openshift` | only when no other stack is found |
| `container` | Dockerfile / Compose only | markers `docker`, `docker-compose` | only when no other stack is found; built with docker (assumed: docker) |
| `sql-scripts` | SQL scripts only | files `*.sql` | only when no other stack is found |
| `scripts` | Scripts only (shell, PowerShell, batch, Python) | files `*.sh`, `*.bash`, `*.ps1`, `*.bat`, `*.cmd`, `*.py`, `*.pl`, `*.groovy` | only when no other stack is found |

## Build tools

50 values.

| Value | What it is | Found from | Notes |
|---|---|---|---|
| `maven` | Maven | files `mvnw`, `mvnw.cmd`; tasks `Maven`, `ArtifactoryMaven`, `JFrogMaven`; commands `mvn`, `mvnw` | stack without repo files: `java-maven` |
| `gradle` | Gradle | files `gradlew`, `gradlew.bat`; tasks `Gradle`, `ArtifactoryGradle`, `JFrogGradle`; commands `gradle`, `gradlew` | stack without repo files: `java-gradle` |
| `ant` | Ant | tasks `Ant`; commands `ant` | stack without repo files: `java-ant` |
| `sbt` | sbt | commands `sbt` | stack without repo files: `scala-sbt` |
| `msbuild` | MSBuild / Visual Studio build (Windows) | tasks `VSBuild`, `MSBuild`, `XamarinAndroid`, `XamariniOS`; commands `msbuild` | stack without repo files: `dotnet-framework` |
| `dotnet` | dotnet CLI | tasks `DotNetCoreCLI`; commands `dotnet build`, `dotnet test`, `dotnet publish`, `dotnet pack`, `dotnet restore`, `dotnet run`, `dotnet msbuild` | stack without repo files: `dotnet` |
| `nuget` | NuGet CLI (restore / pack / push) | files `packages.config`; tasks `NuGetCommand`, `NuGetRestore`, `NuGetInstaller`, `NuGet`, `NuGetPackager`, `NuGetPublisher`, `ArtifactoryNuGet`; commands `nuget restore`, `nuget pack`, `nuget push`, `nuget install` |  |
| `cake` | Cake build script | files `build.cake`; tasks `Cake`; commands `cake`, `dotnet cake`, `dotnet-cake` |  |
| `nuke` | NUKE build | files `.nuke`, `.nuke/parameters.json`; commands `nuke` |  |
| `psake` | psake (PowerShell build) | files `psakefile.ps1`; commands `Invoke-psake` |  |
| `devenv` | Visual Studio IDE build (devenv, Windows) | commands `devenv` |  |
| `ssis-build` | SSIS build task | tasks `SSISBuild` | stack without repo files: `ssis` |
| `npm` | npm | files `package-lock.json`, `npm-shrinkwrap.json`; tasks `Npm`, `ArtifactoryNpm`, `JFrogNpm`; commands `npm ci`, `npm install`, `npm i`, `npm run`, `npm test`, `npm publish`, `npm pack`, `npx` | stack without repo files: `node` |
| `yarn` | Yarn | files `yarn.lock`, `.yarnrc.yml`; tasks `Yarn`; commands `yarn` | stack without repo files: `node` |
| `pnpm` | pnpm | files `pnpm-lock.yaml`; commands `pnpm` | stack without repo files: `node` |
| `angular-cli` | Angular CLI (ng) | commands `ng build`, `ng test`, `ng lint`, `ng e2e` | stack without repo files: `angular` |
| `bower` | Bower (legacy) | files `bower.json`; commands `bower install` |  |
| `grunt` | Grunt | files `Gruntfile.js`, `Gruntfile.coffee`; tasks `Grunt`; commands `grunt` | stack without repo files: `node` |
| `gulp` | Gulp | files `gulpfile.js`, `gulpfile.ts`, `gulpfile.babel.js`; tasks `Gulp`; commands `gulp` | stack without repo files: `node` |
| `pip` | pip | tasks `PipAuthenticate`; commands `pip install`, `pip3 install`, `pip wheel`; script regex `python3?(?:\.exe)?\s+-m\s+pip\s+install` | stack without repo files: `python` |
| `poetry` | Poetry | files `poetry.lock`; commands `poetry` | stack without repo files: `python` |
| `pipenv` | Pipenv | files `Pipfile.lock`; commands `pipenv` | stack without repo files: `python` |
| `conda` | Conda / Mamba | files `environment.yml`, `environment.yaml`; tasks `CondaEnvironment`; commands `conda install`, `conda create`, `conda env`, `mamba`, `micromamba` | stack without repo files: `python` |
| `uv` | uv | files `uv.lock`; commands `uv sync`, `uv pip`, `uv run`, `uv build` | stack without repo files: `python` |
| `go` | Go toolchain | tasks `Go`, `GoTool`; commands `go build`, `go test`, `go mod`, `go vet`, `go install`, `goreleaser` | stack without repo files: `go` |
| `cargo` | Cargo | files `Cargo.lock`; commands `cargo` | stack without repo files: `rust` |
| `composer` | Composer | files `composer.lock`; commands `composer install`, `composer update` | stack without repo files: `php` |
| `bundler` | Bundler / Rake | files `Gemfile.lock`, `Rakefile`; commands `bundle install`, `bundle exec`, `rake` | stack without repo files: `ruby` |
| `cmake` | CMake | tasks `CMake`; commands `cmake`, `ctest` | stack without repo files: `cpp-cmake` |
| `make` | Make | files `Makefile`, `GNUmakefile`; commands `make`, `nmake`, `gmake` |  |
| `bazel` | Bazel | files `WORKSPACE`, `WORKSPACE.bazel`, `MODULE.bazel`, `BUILD.bazel`; commands `bazel`, `bazelisk` |  |
| `xcodebuild` | Xcode build (macOS) | tasks `Xcode`; commands `xcodebuild` | stack without repo files: `ios` |
| `fastlane` | fastlane | files `fastlane/Fastfile`, `Fastfile`; commands `fastlane` |  |
| `cocoapods` | CocoaPods | files `Podfile.lock`; tasks `CocoaPods`; commands `pod install` |  |
| `flutter` | Flutter CLI | tasks `FlutterBuild`, `FlutterInstall`, `FlutterTest`, `FlutterCommand`; commands `flutter build`, `flutter test`, `flutter pub` | stack without repo files: `flutter` |
| `docker` | Docker build | task `Docker` with command = build / push / buildAndPush / (unset); task `DockerCompose` with action = build; commands `docker build`, `docker buildx`, `docker-compose build`, `docker compose build` | stack without repo files: `container` |
| `buildah` | Buildah | commands `buildah bud`, `buildah build` | stack without repo files: `container` |
| `podman` | Podman | commands `podman build` | stack without repo files: `container` |
| `kaniko` | Kaniko | script regex `/kaniko/executor\|\bexecutor\s+--context` | stack without repo files: `container` |
| `jib` | Jib (Maven / Gradle plugin) | script regex `jib:(?:build\|dockerBuild\|buildTar)\|gradlew?(?:\.bat)?\s+(?:\S+\s+)*?jib(?:DockerBuild\|BuildTar)?(?=\s\|$)` |  |
| `openshift-build` | OpenShift build (S2I / BuildConfig) | commands `oc start-build`, `oc new-build`, `s2i build` |  |
| `buildpacks` | Cloud Native Buildpacks | commands `pack build`; script regex `spring-boot:build-image\|bootBuildImage` |  |
| `packer` | Packer | tasks `PackerBuild`; commands `packer build` | stack without repo files: `packer` |
| `terraform` | Terraform CLI | tasks `TerraformTaskV1`, `TerraformTaskV2`, `TerraformTaskV3`, `TerraformTaskV4`, `TerraformTaskV5`, `TerraformCLI`, `TerraformInstaller`; commands `terraform init`, `terraform plan`, `terraform apply`, `terraform validate`, `terragrunt` | stack without repo files: `terraform` |
| `helm` | Helm (lint / package) | task `HelmDeploy` with command = package / save / push / lint / dependency / template; commands `helm package`, `helm lint`, `helm template`, `helm dependency`, `helm push` | stack without repo files: `helm-charts` |
| `mkdocs` | MkDocs | commands `mkdocs build`, `mkdocs gh-deploy` | stack without repo files: `docs` |
| `docfx` | DocFX | commands `docfx` | stack without repo files: `docs` |
| `sphinx` | Sphinx | commands `sphinx-build` | stack without repo files: `docs` |
| `hugo` | Hugo | commands `hugo` | stack without repo files: `docs` |
| `jekyll` | Jekyll | commands `jekyll build` | stack without repo files: `docs` |

## Test & scan tools

38 values.

| Value | What it is | Found from | Notes |
|---|---|---|---|
| `sonarqube` | SonarQube | files `sonar-project.properties`; tasks `SonarQubePrepare`, `SonarQubeAnalyze`, `SonarQubePublish`; commands `sonar-scanner`, `dotnet sonarscanner`, `dotnet-sonarscanner`, `SonarScanner.MSBuild`; script regex `sonar:sonar\|org\.sonarsource\|gradlew?(?:\.bat)?\s+(?:\S+\s+)*?sonar(?:qube)?(?=\s\|$)`; connection type `sonarqube` |  |
| `sonarcloud` | SonarCloud | tasks `SonarCloudPrepare`, `SonarCloudAnalyze`, `SonarCloudPublish`; connection type `sonarcloud` |  |
| `checkmarx` | Checkmarx | tasks `Application security testing`, `Checkmarx`, `Checkmarx AST`, `CxScan`; commands `cx scan`, `cxflow`, `runCxConsole` |  |
| `fortify` | Fortify (SCA / ScanCentral / on Demand) | tasks `FortifySCA`, `FortifyScanCentralSAST`, `FortifyScanCentralDAST`, `FortifyOnDemandStatic`, `FortifyOnDemandDynamic`; commands `sourceanalyzer`, `scancentral`, `fcli`, `FoDUploader` |  |
| `veracode` | Veracode | tasks `Veracode`, `VeracodePipelineScan`, `Veracode Upload And Scan`, `VeracodeFlawImporter`; script regex `pipeline-scan\.jar\|veracode` |  |
| `mend` | Mend (WhiteSource) | tasks `WhiteSource`, `WhiteSourceBolt`, `Mend`; script regex `wss-unified-agent\|\bmend\s+(?:ua\|sca\|dep)\b\|whitesource` |  |
| `snyk` | Snyk | tasks `SnykSecurityScan`; commands `snyk test`, `snyk monitor`, `snyk container`, `snyk code`, `snyk iac` |  |
| `blackduck` | Black Duck / Synopsys Detect | tasks `SynopsysDetectTask`, `BlackDuckDetectTask`, `BlackDuckSecurityScan`, `Black Duck Detect`; script regex `synopsys-detect\|\bdetect\d*\.(?:sh\|ps1)\b\|detect-\d[\d.]*\.jar\|blackduck` |  |
| `coverity` | Coverity | tasks `SynopsysCoverity`; commands `cov-build`, `cov-analyze`, `cov-capture` |  |
| `dependency-check` | OWASP Dependency-Check | tasks `dependency-check-build-task`; script regex `dependency-check\|dependencyCheckAnalyze` |  |
| `trivy` | Trivy | tasks `trivy`; commands `trivy image`, `trivy fs`, `trivy config`, `trivy repo`, `trivy k8s` |  |
| `anchore` | Anchore (Grype / Syft) | commands `grype`, `syft`, `anchore-cli` |  |
| `aqua` | Aqua Security | tasks `aquasecScanner`; commands `scannercli` |  |
| `prisma-cloud` | Prisma Cloud (twistcli) | tasks `prisma-cloud-compute-scan`; commands `twistcli` |  |
| `jfrog-xray` | JFrog Xray | tasks `JFrogBuildScan`, `ArtifactoryXrayScan`, `JFrogAudit`; commands `jf audit`, `jf scan`, `jf bs`, `jfrog rt bs` |  |
| `microsoft-security` | Microsoft Security Code Analysis / Security DevOps (CredScan, BinSkim, ...) | tasks `MicrosoftSecurityDevOps`, `CredScan`, `BinSkim`, `RoslynAnalyzers`, `PostAnalysis`, `SdtReport`, `PublishSecurityAnalysisLogs`, `AntiMalware`, `ComponentGovernanceComponentDetection` |  |
| `codeql` | CodeQL / Advanced Security | tasks `AdvancedSecurity-Codeql-Init`, `AdvancedSecurity-Codeql-Autobuild`, `AdvancedSecurity-Codeql-Analyze`, `AdvancedSecurity-Dependency-Scanning`; commands `codeql database`, `codeql analyze` |  |
| `secret-scan` | Secret scanning (gitleaks, TruffleHog, detect-secrets) | files `.gitleaks.toml`, `.secrets.baseline`; commands `gitleaks`, `trufflehog`, `detect-secrets` |  |
| `iac-scan` | IaC scanning (Checkov, tfsec, Terrascan, KICS, TFLint) | files `.tflint.hcl`, `.checkov.yml`, `.checkov.yaml`; commands `checkov`, `tfsec`, `terrascan`, `kics`, `tflint` |  |
| `zap` | OWASP ZAP (DAST) | tasks `owaspzap`, `OWASPZAP`; script regex `zap-(?:baseline\|full-scan\|api-scan)\.py\|zap\.sh\|owasp/zap\|zaproxy` |  |
| `code-coverage` | Code coverage report (Cobertura / JaCoCo) | tasks `PublishCodeCoverageResults`; commands `reportgenerator` |  |
| `vstest` | VSTest (Windows) | tasks `VSTest`, `VSTestPlatformInstaller`, `VisualStudioTestPlatformInstaller`; commands `vstest.console` |  |
| `dotnet-test` | dotnet test | task `DotNetCoreCLI` with command = test; commands `dotnet test` |  |
| `azure-test-plans` | Azure Test Plans runs (no GitLab equivalent) | task `VSTest` with testSelector = testPlan |  |
| `karma` | Karma (needs a headless browser) | files `karma.conf.js`, `karma.conf.ts`; files `angular.json` with content check `:karma"`; files `package.json` with content check `"karma"\s*:`; commands `karma start` |  |
| `jest` | Jest | files `jest.config.js`, `jest.config.ts`, `jest.config.mjs`, `jest.config.cjs`, `jest.config.json`; files `package.json` with content check `"jest"\s*:`; commands `jest` |  |
| `vitest` | Vitest | files `vitest.config.*`; files `package.json` with content check `"vitest"\s*:`; commands `vitest` |  |
| `mocha` | Mocha | files `.mocharc*`; files `package.json` with content check `"mocha"\s*:`; commands `mocha` |  |
| `cypress` | Cypress (needs the Cypress image) | files `cypress.config.*`, `cypress.json`; files `package.json` with content check `"cypress"\s*:`; commands `cypress run` |  |
| `playwright` | Playwright (needs the Playwright image) | files `playwright.config.*`; files `package.json` with content check `"@playwright/test"\s*:`; files `*.csproj` with content check `Microsoft\.Playwright`; files `requirements*.txt`, `pyproject.toml` with content check `\bplaywright\b`; commands `playwright test` |  |
| `protractor` | Protractor (deprecated end-to-end tests) | files `protractor.conf.js`; files `package.json` with content check `"protractor"\s*:`; commands `protractor` |  |
| `selenium` | Selenium / WebDriver | files `*.csproj`, `pom.xml`, `build.gradle`, `build.gradle.kts`, `requirements*.txt`, `pyproject.toml`, `package.json` with content check `selenium` |  |
| `pytest` | pytest | files `pytest.ini`, `conftest.py`; files `pyproject.toml`, `setup.cfg`, `tox.ini` with content check `\[tool\.pytest\|\[pytest\]\|\[tool:pytest\]`; commands `pytest`, `py.test` |  |
| `newman` | Postman / Newman API tests | files `*.postman_collection.json`; tasks `NewmanPostman`, `newman`; commands `newman run` |  |
| `jmeter` | JMeter load tests | files `*.jmx`; tasks `JMeter`, `JMeterInstaller`, `Taurus`; commands `jmeter` |  |
| `k6` | k6 load tests | tasks `k6-load-test`; commands `k6 run` |  |
| `gatling` | Gatling load tests | files `pom.xml`, `build.gradle`, `build.gradle.kts`, `build.sbt` with content check `gatling`; script regex `gatling` |  |
| `app-center-test` | App Center Test (retired) | tasks `AppCenterTest` |  |

## Deploy targets

56 values.

| Value | What it is | Found from | Notes |
|---|---|---|---|
| `openshift` | OpenShift | tasks `oc-cmd`, `oc-setup`, `oc-conditional-cmd`, `config-map`; commands `oc apply`, `oc rollout`, `oc process`, `oc new-app`, `oc set`, `oc replace`, `oc create`, `oc tag`, `oc import-image`, `oc patch`, `oc login`; connection type `openshift` |  |
| `kubernetes` | Kubernetes (kubectl / Helm / Kustomize) | tasks `KubernetesManifest`, `Kubernetes`; task `HelmDeploy` with command = install / upgrade / rollback / delete / uninstall; commands `kubectl apply`, `kubectl rollout`, `kubectl set image`, `kubectl replace`, `kubectl create`, `kubectl patch`, `kubectl delete`, `helm upgrade`, `helm install`, `helm rollback`, `helm uninstall`, `kustomize build`, … (+1); connection type `kubernetes` |  |
| `gitops` | GitOps (Argo CD / Flux) | commands `argocd`, `flux reconcile`, `flux create`, `kustomize edit set image` |  |
| `docker-host` | Docker host / Swarm | commands `docker stack deploy`, `docker context use`; script regex `DOCKER_HOST=\|docker(?:-compose)?\s+(?:-H\|--host)\s` |  |
| `iis` | IIS (Web Deploy / IIS tasks) | tasks `IISWebAppDeploymentOnMachineGroup`, `IISWebAppManagementOnMachineGroup`, `IISWebAppDeployment`, `IISWebAppMgmt`; commands `msdeploy`, `appcmd`, `New-WebSite`, `New-WebAppPool`, `Stop-WebAppPool`, `Start-WebAppPool`, `Restart-WebAppPool`, `Stop-WebSite`, `Start-WebSite`; script regex `WebAdministration\|IIS:\\` |  |
| `windows-service` | Windows service | commands `sc create`, `sc config`, `sc start`, `sc stop`, `sc delete`, `New-Service`, `Start-Service`, `Stop-Service`, `Restart-Service`, `Set-Service`, `Remove-Service`, `nssm`, … (+1) |  |
| `windows-vm` | Windows servers over WinRM / remote file copy | tasks `PowerShellOnTargetMachines`, `WindowsMachineFileCopy`; script regex `Invoke-Command\s+[^\n]*-ComputerName\|New-PSSession\|Enter-PSSession\|-ToSession\b` |  |
| `deployment-group` | Deployment group agents on the target servers | deployment-group jobs |  |
| `linux-vm` | Linux servers over SSH | tasks `SSH`, `CopyFilesOverSSH`; commands `scp`, `rsync`, `sshpass`; script regex `\bssh\s+(?:-\S+\s+)*[\w.-]+@[\w.-]+`; connection type `ssh` |  |
| `file-share` | Windows file share (UNC path) | script regex `(?:^\|[\s"'=])\\\\[\w.$-]+\\[\w.$-]+` |  |
| `ftp` | FTP / SFTP upload | tasks `FtpUpload`; commands `lftp`, `sftp`, `winscp`; script regex `ftps?://` |  |
| `tomcat` | Apache Tomcat | script regex `/manager/(?:text/)?deploy\|catalina\.(?:sh\|bat)\|tomcat-manager\|(?:cargo\|tomcat7?):(?:deploy\|redeploy)` |  |
| `jboss-wildfly` | JBoss EAP / WildFly | commands `jboss-cli`; script regex `wildfly:deploy\|standalone\.(?:sh\|bat)` |  |
| `weblogic` | WebLogic | script regex `weblogic\.Deployer\|\bwlst(?:\.sh\|\.cmd)?\b\|weblogic-maven-plugin` |  |
| `websphere` | WebSphere | script regex `\bwsadmin(?:\.sh\|\.bat)?\b\|was-maven-plugin\|websphere` |  |
| `service-fabric` | Service Fabric | tasks `ServiceFabricDeploy`, `ServiceFabricComposeDeploy`, `ServiceFabricPowerShell`; connection type `servicefabric` |  |
| `database` | Database deployment (DACPAC, SQL scripts, Flyway, Liquibase, migrations) | tasks `SqlAzureDacpacDeployment`, `SqlDacpacDeploymentOnMachineGroup`, `SqlServerDacpacDeployment`, `MysqlDeploymentOnMachineGroup`, `AzureMysqlDeployment`; commands `sqlpackage`, `sqlcmd`, `Invoke-Sqlcmd`, `flyway migrate`, `flyway repair`, `flyway baseline`, `liquibase update`, `liquibase rollback`, `dotnet ef database update`, `alembic upgrade`, `manage.py migrate`, `rails db:migrate`, … (+4) |  |
| `ssis-catalog` | SSIS catalog | tasks `SSISDeploy`; commands `ISDeploymentWizard` |  |
| `ssrs-server` | SSRS report server | script regex `ReportingServicesTools\|Write-RsCatalogItem\|Write-RsFolderContent\|Publish-RsProject` |  |
| `power-bi` | Power BI service | tasks `PowerBIActions`; script regex `MicrosoftPowerBIMgmt\|Connect-PowerBIServiceAccount\|New-PowerBIReport` |  |
| `power-platform` | Power Platform environment | tasks `PowerPlatformImportSolution`, `PowerPlatformDeployPackage`, `PowerPlatformPublishCustomizations`, `PowerPlatformApplySolutionUpgrade`; commands `pac solution import`, `pac package deploy` |  |
| `salesforce` | Salesforce org | commands `sfdx force:source:deploy`, `sfdx force:mdapi:deploy`, `sf project deploy`, `sf deploy` |  |
| `databricks` | Databricks workspace | commands `databricks workspace`, `databricks jobs`, `databricks bundle`, `databricks fs`, `databricks repos` |  |
| `azure-app-service` | Azure App Service | tasks `AzureRmWebAppDeployment`, `AzureWebApp`, `AzureWebAppContainer`, `AzureAppServiceManage`, `AzureAppServiceSettings`; commands `az webapp` | replaces `azure` |
| `azure-functions` | Azure Functions | tasks `AzureFunctionApp`, `AzureFunctionAppContainer`, `AzureFunctionOnKubernetes`; commands `func azure functionapp publish`, `az functionapp` | replaces `azure` |
| `azure-container-apps` | Azure Container Apps | tasks `AzureContainerApps`; commands `az containerapp` | replaces `azure` |
| `azure-static-web-apps` | Azure Static Web Apps | tasks `AzureStaticWebApp`; commands `swa deploy`, `az staticwebapp` | replaces `azure` |
| `azure-storage` | Azure Storage (blob / file copy) | tasks `AzureFileCopy`; commands `azcopy`, `az storage blob upload`, `az storage blob upload-batch`, `az storage blob sync`, `az storage file upload` | replaces `azure` |
| `azure-infra` | Azure ARM / Bicep deployment | tasks `AzureResourceManagerTemplateDeployment`, `AzureResourceGroupDeployment`; commands `az deployment`, `az group deployment`, `New-AzResourceGroupDeployment`, `New-AzDeployment`, `az bicep` | replaces `azure` |
| `azure-vm` | Azure VM / scale set | tasks `AzureVmssDeployment`; commands `az vmss`, `az vm run-command` | replaces `azure` |
| `azure-cloud-services` | Azure Cloud Services (classic) | tasks `AzureCloudPowerShellDeployment` | replaces `azure` |
| `azure-spring-apps` | Azure Spring Apps | tasks `AzureSpringCloud`; commands `az spring` | replaces `azure` |
| `azure` | Azure (CLI / PowerShell scripts) | tasks `AzureCLI`, `AzurePowerShell` |  |
| `aws-s3` | AWS S3 | tasks `S3Upload`; commands `aws s3` | replaces `aws` |
| `aws-lambda` | AWS Lambda / SAM / Serverless | tasks `LambdaDeployFunction`, `LambdaNETCoreDeploy`; commands `aws lambda`, `sam deploy`, `serverless deploy`, `sls deploy` | replaces `aws` |
| `aws-ecs` | AWS ECS | commands `aws ecs`, `ecs-cli` | replaces `aws` |
| `aws-cloudformation` | AWS CloudFormation / CDK | tasks `CloudFormationCreateOrUpdateStack`, `CloudFormationExecuteChangeSet`, `CloudFormationDeleteStack`; commands `aws cloudformation`, `cdk deploy` | replaces `aws` |
| `aws-codedeploy` | AWS CodeDeploy | tasks `CodeDeployDeployApplication`; commands `aws deploy` | replaces `aws` |
| `aws-beanstalk` | AWS Elastic Beanstalk | tasks `BeanstalkDeployApplication`, `BeanstalkCreateApplicationVersion`; commands `aws elasticbeanstalk`, `eb deploy` | replaces `aws` |
| `aws` | AWS (CLI / tools) | tasks `AWSCLI`, `AWSShellScript`, `AWSPowerShellModuleScript`, `SystemsManagerRunCommand`; commands `aws`; connection type `aws` |  |
| `gcp` | Google Cloud | commands `gcloud app`, `gcloud run`, `gcloud functions`, `gcloud container`, `gcloud compute`, `gcloud deploy`, `gsutil` |  |
| `cloud-foundry` | Cloud Foundry | tasks `CloudFoundry`, `CloudFoundryCLI`; commands `cf push`, `cf bgd`, `cf blue-green-deploy`, `cf zero-downtime-push` |  |
| `terraform` | Terraform apply | task `TerraformTaskV1` with command = apply / destroy; task `TerraformTaskV2` with command = apply / destroy; task `TerraformTaskV3` with command = apply / destroy; task `TerraformTaskV4` with command = apply / destroy; task `TerraformTaskV5` with command = apply / destroy; task `TerraformCLI` with command = apply / destroy; commands `terraform apply`, `terraform destroy`, `terragrunt apply`, `terragrunt run-all` |  |
| `pulumi` | Pulumi | tasks `Pulumi`; commands `pulumi up`, `pulumi destroy` |  |
| `ansible` | Ansible (playbooks, AWX / Tower) | tasks `Ansible`; commands `ansible-playbook`, `ansible`, `awx job_templates`, `tower-cli` |  |
| `chef` | Chef | tasks `Chef`, `ChefKnife`; commands `knife`, `chef-client` |  |
| `puppet` | Puppet | commands `puppet apply`, `puppet agent`, `r10k`, `bolt` |  |
| `octopus` | Octopus Deploy | tasks `OctopusCreateRelease`, `OctopusDeployRelease`, `OctopusPromote`, `OctopusPush`, `OctopusPack`, `OctopusMetadata`, `OctopusBuildInformation`, `OctopusRunRunbook`, `OctoInstaller`; commands `octo create-release`, `octo deploy-release`, `octo push`, `octo pack`, `octopus release`, `octopus package`; connection type `octopusendpoint` |  |
| `urbancode` | UrbanCode Deploy | commands `udclient` |  |
| `xl-deploy` | Digital.ai (XebiaLabs) Deploy | tasks `XLDeploy`; commands `xld`, `xlw` |  |
| `jenkins` | Jenkins jobs (queued from Azure DevOps) | tasks `JenkinsQueueJob`, `JenkinsDownloadArtifacts`; connection type `jenkins` |  |
| `app-center` | App Center distribution (retired March 2025) | tasks `AppCenterDistribute`, `HockeyApp`; commands `appcenter distribute` |  |
| `app-store` | Apple App Store / TestFlight | tasks `AppStoreRelease`, `AppStorePromote`; commands `fastlane deliver`, `fastlane pilot`, `fastlane upload_to_testflight`, `fastlane upload_to_app_store`, `altool` |  |
| `google-play` | Google Play | tasks `GooglePlayRelease`, `GooglePlayPromote`, `GooglePlayIncreaseRollout`, `GooglePlayReleaseBundle`, `GooglePlayStatusUpdate`; commands `fastlane supply`, `fastlane upload_to_play_store` |  |
| `firebase` | Firebase (App Distribution / Hosting) | commands `firebase appdistribution`, `firebase deploy` |  |
| `microsoft-store` | Microsoft Store | tasks `store-publish`, `store-flight` |  |

## Artifacts

15 values.

| Value | What it is | Found from | Notes |
|---|---|---|---|
| `image` | Container image | markers `docker`; tasks `ECRPushImage`; task `Docker` with command = build / push / buildAndPush / (unset); task `DockerCompose` with action = build / push; commands `docker build`, `docker push`, `docker buildx`, `podman build`, `podman push`, `buildah bud`, `buildah build`, `buildah push`, `az acr build`, `oc start-build`, `pack build`, `s2i build`, … (+2); script regex `/kaniko/executor\|jib:(?:build\|dockerBuild)\|bootBuildImage\|spring-boot:build-image` |  |
| `helm-chart` | Helm chart (packaged / pushed) | task `HelmDeploy` with command = package / save / push; commands `helm package`, `helm push`, `helm cm-push`, `helm chart save`, `helm chart push` |  |
| `maven-package` | Maven / Gradle package deployed to a Maven repository | task `Maven` with goals = deploy / deploy:deploy-file / release:perform; task `Gradle` with tasks = publish / uploadArchives / artifactoryPublish; script regex `\bmvnw?(?:\.cmd)?\s+(?:[^\n;&\|]*\s)?deploy(?::deploy(?:-file)?)?(?=\s\|$)\|\bgradlew?(?:\.bat)?\s+(?:[^\n;&\|]*\s)?(?:publish(?!ToMavenLocal)\w*\|uploadArchives\|artifactoryPublish)(?=\s\|$)` |  |
| `nuget-package` | NuGet package | tasks `NuGetPackager`, `NuGetPublisher`; task `NuGetCommand` with command = pack / push; task `DotNetCoreCLI` with command = pack / push; commands `nuget pack`, `nuget push`, `dotnet pack`, `dotnet nuget push` |  |
| `npm-package` | npm package | task `Npm` with command = publish; commands `npm publish`, `yarn publish`, `pnpm publish`, `yarn npm publish` |  |
| `python-package` | Python package (wheel / sdist) | tasks `TwineAuthenticate`; commands `twine upload`, `poetry publish`, `poetry build`, `flit publish`, `uv publish`, `uv build`, `hatch publish`, `hatch build`; script regex `python3?(?:\.exe)?\s+-m\s+build\b\|setup\.py\s+(?:sdist\|bdist_wheel)` |  |
| `universal-package` | Universal package (Azure Artifacts) | task `UniversalPackages` with command = publish; commands `az artifacts universal publish` |  |
| `generic-upload` | Generic upload to Artifactory / Nexus | tasks `ArtifactoryGenericUpload`; task `JFrogGenericArtifacts` with command = upload; commands `jf rt upload`, `jf rt u`, `jfrog rt upload`, `jfrog rt u`; script regex `curl\s[^\n]*(?:\s-T\|--upload-file)\s` |  |
| `chocolatey-package` | Chocolatey package | commands `choco pack`, `choco push` |  |
| `symbols` | Debug symbols (symbol server) | tasks `PublishSymbols` |  |
| `mobile-app` | Mobile app package (APK / AAB / IPA) | tasks `AndroidSigning`, `XamarinAndroid`, `XamariniOS`; task `Xcode` with packageApp = true; commands `flutter build apk`, `flutter build appbundle`, `flutter build ipa`, `fastlane gym`, `fastlane build_app`; script regex `\bassemble(?:Release\|Debug)\b\|\bbundleRelease\b\|-exportArchive` |  |
| `installer` | Windows installer (MSI / MSIX / setup.exe) | files `*.wixproj`, `*.wxs`, `*.vdproj`, `*.iss`, `*.nsi`, `*.aip`, `*.wapproj`; script regex `\b(?:candle\|light)\.exe\b\|\bwix\s+build\b\|\bmakensis\b\|\biscc(?:\.exe)?\b\|\bmakeappx(?:\.exe)?\b` |  |
| `dacpac` | Database package (DACPAC / BACPAC) | files `*.sqlproj`; script regex `\.[db]acpac\b\|/Action:(?:Extract\|Export)` |  |
| `vm-image` | VM image (Packer) | tasks `PackerBuild`; commands `packer build` |  |
| `files` | Build artifacts (zip / drop folder) | tasks `PublishBuildArtifacts`, `PublishPipelineArtifact`, `ArchiveFiles`, `publish`; script regex `##vso\[artifact\.upload` |  |

## Markers

26 values.

| Value | What it is | Found from | Notes |
|---|---|---|---|
| `docker` | Dockerfile | files `Dockerfile`, `*.Dockerfile`, `Dockerfile.*`, `Containerfile`, `Containerfile.*` |  |
| `docker-compose` | Docker Compose file | files `docker-compose*.yml`, `docker-compose*.yaml`, `compose.yml`, `compose.yaml`, `compose.*.yml`, `compose.*.yaml` |  |
| `helm` | Helm chart (Chart.yaml) | files `Chart.yaml` |  |
| `kustomize` | Kustomize configuration | files `kustomization.yaml`, `kustomization.yml`, `Kustomization` |  |
| `k8s-manifests` | Kubernetes manifests | files `*k8s*/*.yaml`, `*k8s*/*.yml`, `*kube*/*.yaml`, `*kube*/*.yml`, `*manifest*/*.yaml`, `*manifest*/*.yml`, `*deploy*/*.yaml`, `*deploy*/*.yml`, `*.k8s.yaml`, `*.k8s.yml`, `deployment.yaml`, `deployment.yml` with content check `^kind:\s*(Deployment\|StatefulSet\|DaemonSet\|CronJob\|Job\|Service\|Ingress\|ConfigMap\|PersistentVolumeClaim\|HorizontalPodAutoscaler)\s*$` |  |
| `openshift` | OpenShift objects (DeploymentConfig, Route, BuildConfig, Template) | files `*openshift*/*.yaml`, `*openshift*/*.yml`, `*openshift*/*.json`, `*k8s*/*.yaml`, `*k8s*/*.yml`, `*manifest*/*.yaml`, `*manifest*/*.yml`, `*deploy*/*.yaml`, `*deploy*/*.yml`, `*.template.yaml`, `*.template.yml`, `*.template.json` with content check `^kind:\s*(DeploymentConfig\|Route\|BuildConfig\|ImageStream\|Template)\s*$\|"kind"\s*:\s*"(DeploymentConfig\|Route\|BuildConfig\|ImageStream\|Template)"` |  |
| `azure-functions` | Azure Functions project (host.json) | files `host.json` with content check `"version"\s*:\s*"2\.0"\|extensionBundle` |  |
| `serverless` | Serverless Framework (serverless.yml) | files `serverless.yml`, `serverless.yaml`, `serverless.ts`, `serverless.js` |  |
| `aws-sam` | AWS SAM template | files `template.yaml`, `template.yml`, `samconfig.toml` with content check `AWS::Serverless\|default\.deploy` |  |
| `aspnet-web` | ASP.NET / ASP.NET Core web project | files `*.csproj`, `*.vbproj`, `*.fsproj` with content check `Sdk="Microsoft\.NET\.Sdk\.(Web\|BlazorWebAssembly\|Razor)"\|349c5851-65df-11da-9384-00065b846f21\|Microsoft\.AspNetCore\.App`; files `web.config` |  |
| `dotnet-worker` | .NET worker service | files `*.csproj`, `*.vbproj`, `*.fsproj` with content check `Sdk="Microsoft\.NET\.Sdk\.Worker"` |  |
| `spring-boot` | Spring Boot | files `pom.xml`, `build.gradle`, `build.gradle.kts` with content check `spring-boot` |  |
| `quarkus` | Quarkus | files `pom.xml`, `build.gradle`, `build.gradle.kts` with content check `io\.quarkus` |  |
| `java-war` | WAR / EAR packaging (application server) | files `pom.xml`, `build.gradle`, `build.gradle.kts` with content check `<packaging>\s*(war\|ear)\s*</packaging>\|(apply plugin:\|id)\s*\(?\s*['"](war\|ear)['"]`; files `*WEB-INF/web.xml` |  |
| `django` | Django | files `manage.py` with content check `django`; files `requirements*.txt`, `pyproject.toml`, `Pipfile`, `setup.py`, `setup.cfg` with content check `\bdjango\b` |  |
| `flask` | Flask | files `requirements*.txt`, `pyproject.toml`, `Pipfile`, `setup.py`, `setup.cfg` with content check `\bflask\b` |  |
| `fastapi` | FastAPI | files `requirements*.txt`, `pyproject.toml`, `Pipfile`, `setup.py`, `setup.cfg` with content check `\bfastapi\b` |  |
| `express` | Express (Node.js server) | files `package.json` with content check `"express"\s*:` |  |
| `nestjs` | NestJS | files `nest-cli.json`; files `package.json` with content check `"@nestjs/core"\s*:` |  |
| `js-monorepo` | JavaScript monorepo (Nx, Lerna, Turborepo, Rush, workspaces) | files `nx.json`, `lerna.json`, `turbo.json`, `pnpm-workspace.yaml`, `rush.json`; files `package.json` with content check `"workspaces"\s*:` |  |
| `config-transforms` | Environment-specific config files (Web.*.config, appsettings.*.json, parameters.xml) | files `web.*.config`, `app.*.config`, `appsettings.*.json`, `parameters.xml`, `*.SetParameters.xml`, `*.transform` |  |
| `jenkinsfile` | Jenkinsfile (may also be built by Jenkins) | files `Jenkinsfile`, `*.jenkinsfile`, `Jenkinsfile.*` |  |
| `gitlab-ci` | Already has a .gitlab-ci.yml | files `.gitlab-ci.yml`, `.gitlab-ci.yaml` |  |
| `github-actions` | GitHub Actions workflows | files `.github/workflows/*.yml`, `.github/workflows/*.yaml` |  |
| `other-ci` | Other CI configuration (Travis, CircleCI, Bitbucket, TeamCity, Bamboo, AppVeyor, Drone, Cloud Build, CodeBuild) | files `.travis.yml`, `.circleci/config.yml`, `bitbucket-pipelines.yml`, `.teamcity/settings.kts`, `bamboo-specs/*`, `appveyor.yml`, `.appveyor.yml`, `.drone.yml`, `cloudbuild.yaml`, `cloudbuild.yml`, `buildspec.yml` |  |
| `devcontainer` | Dev container definition | files `.devcontainer/devcontainer.json`, `.devcontainer.json`, `.devcontainer/*/devcontainer.json` |  |

## Named archetypes

143 entries, in rule order. A condition lists ids that must all be present; `none` means that dimension is empty.
How a repo's names are chosen: [Concepts](concepts.md#named-archetypes).

| Name | Proposed template | Conditions |
|---|---|---|
| ASP.NET Core + Angular | `dotnet-angular` | Stack: `dotnet` + `angular` |
| ASP.NET Core + React | `dotnet-react` | Stack: `dotnet` + `react` |
| ASP.NET Core + Vue | `dotnet-vue` | Stack: `dotnet` + `vue` |
| ASP.NET (.NET Framework) + Angular | `dotnet-framework-angular` | Stack: `dotnet-framework` + `angular` |
| ASP.NET (.NET Framework) + AngularJS | `dotnet-framework-angularjs` | Stack: `dotnet-framework` + `angularjs` |
| ASP.NET (.NET Framework) + React | `dotnet-framework-react` | Stack: `dotnet-framework` + `react` |
| Java/Maven + Angular | `java-maven-angular` | Stack: `java-maven` + `angular` |
| Java/Maven + React | `java-maven-react` | Stack: `java-maven` + `react` |
| Java/Maven + Vue | `java-maven-vue` | Stack: `java-maven` + `vue` |
| Java/Gradle + Angular | `java-gradle-angular` | Stack: `java-gradle` + `angular` |
| Java/Gradle + React | `java-gradle-react` | Stack: `java-gradle` + `react` |
| Python + React | `python-react` | Stack: `python` + `react` |
| Python + Angular | `python-angular` | Stack: `python` + `angular` |
| Ionic / Capacitor + Angular app | `ionic-angular` | Stack: `hybrid-mobile` + `angular`; also covers `android`, `ios` |
| .NET Framework -> IIS (Windows) | `dotnet-framework-iis` | Stack: `dotnet-framework`; Deploy targets: `iis` |
| .NET Framework -> Windows service | `dotnet-framework-winservice` | Stack: `dotnet-framework`; Deploy targets: `windows-service` |
| .NET Framework -> Azure App Service | `dotnet-framework-appservice` | Stack: `dotnet-framework`; Deploy targets: `azure-app-service` |
| .NET Framework -> Service Fabric | `dotnet-service-fabric` | Stack: `dotnet-framework`; Deploy targets: `service-fabric` |
| .NET Framework -> Octopus Deploy | `dotnet-framework-octopus` | Stack: `dotnet-framework`; Deploy targets: `octopus` |
| .NET Framework library (NuGet) | `dotnet-framework-nuget` | Stack: `dotnet-framework`; Artifacts: `nuget-package` |
| .NET Framework app (installer) | `dotnet-framework-installer` | Stack: `dotnet-framework`; Artifacts: `installer` |
| .NET Framework build (Windows) | `dotnet-framework-build` | Stack: `dotnet-framework` |
| .NET -> container -> OpenShift | `dotnet-openshift` | Stack: `dotnet`; Deploy targets: `openshift`; Artifacts: `image` |
| .NET -> container -> Kubernetes | `dotnet-k8s` | Stack: `dotnet`; Deploy targets: `kubernetes`; Artifacts: `image` |
| .NET -> container | `dotnet-container` | Stack: `dotnet`; Artifacts: `image` |
| .NET -> Azure App Service | `dotnet-appservice` | Stack: `dotnet`; Deploy targets: `azure-app-service` |
| .NET -> Azure Functions | `dotnet-functions` | Stack: `dotnet`; Deploy targets: `azure-functions` |
| .NET -> IIS | `dotnet-iis` | Stack: `dotnet`; Deploy targets: `iis` |
| .NET -> Windows service | `dotnet-winservice` | Stack: `dotnet`; Deploy targets: `windows-service` |
| .NET -> Linux VM (SSH) | `dotnet-vm` | Stack: `dotnet`; Deploy targets: `linux-vm` |
| .NET -> Service Fabric | `dotnet-service-fabric` | Stack: `dotnet`; Deploy targets: `service-fabric` |
| .NET -> Octopus Deploy | `dotnet-octopus` | Stack: `dotnet`; Deploy targets: `octopus` |
| .NET package/library | `dotnet-package` | Stack: `dotnet`; Artifacts: `nuget-package` |
| .NET build | `dotnet-build` | Stack: `dotnet` |
| .NET project (framework not detected) | `dotnet-build` | Stack: `dotnet-project` |
| WPF / WinForms desktop app (Windows) | `dotnet-desktop` | Stack: `dotnet-desktop`; also covers `dotnet` |
| UWP / WinUI / MSIX app (Windows) | `windows-app` | Stack: `windows-app`; also covers `dotnet` |
| Xamarin app (end of support: move to .NET MAUI) | `xamarin` | Stack: `xamarin`; also covers `dotnet` |
| .NET MAUI app | `dotnet-maui` | Stack: `maui`; also covers `dotnet` |
| Java/Maven -> container -> OpenShift | `java-maven-openshift` | Stack: `java-maven`; Deploy targets: `openshift`; Artifacts: `image` |
| Java/Maven -> container -> Kubernetes | `java-maven-k8s` | Stack: `java-maven`; Deploy targets: `kubernetes`; Artifacts: `image` |
| Java/Maven -> container | `java-maven-container` | Stack: `java-maven`; Artifacts: `image` |
| Java/Maven -> Tomcat | `java-maven-tomcat` | Stack: `java-maven`; Deploy targets: `tomcat` |
| Java/Maven -> JBoss / WildFly | `java-maven-jboss` | Stack: `java-maven`; Deploy targets: `jboss-wildfly` |
| Java/Maven -> WebLogic | `java-maven-weblogic` | Stack: `java-maven`; Deploy targets: `weblogic` |
| Java/Maven -> WebSphere | `java-maven-websphere` | Stack: `java-maven`; Deploy targets: `websphere` |
| Java/Maven -> Linux VM (SSH) | `java-maven-vm` | Stack: `java-maven`; Deploy targets: `linux-vm` |
| Java/Maven -> Azure App Service | `java-maven-appservice` | Stack: `java-maven`; Deploy targets: `azure-app-service` |
| Java/Maven library (Maven repository) | `java-maven-library` | Stack: `java-maven`; Artifacts: `maven-package` |
| Java/Maven library or app (no deploy) | `java-maven-build` | Stack: `java-maven`; Deploy targets: `none` |
| Java/Maven | `java-maven-build` | Stack: `java-maven` |
| Java/Gradle -> container -> OpenShift | `java-gradle-openshift` | Stack: `java-gradle`; Deploy targets: `openshift`; Artifacts: `image` |
| Java/Gradle -> container -> Kubernetes | `java-gradle-k8s` | Stack: `java-gradle`; Deploy targets: `kubernetes`; Artifacts: `image` |
| Java/Gradle -> container | `java-gradle-container` | Stack: `java-gradle`; Artifacts: `image` |
| Java/Gradle library (Maven repository) | `java-gradle-library` | Stack: `java-gradle`; Artifacts: `maven-package` |
| Java/Gradle library or app (no deploy) | `java-gradle-build` | Stack: `java-gradle`; Deploy targets: `none` |
| Java/Gradle | `java-gradle-build` | Stack: `java-gradle` |
| Java/Ant (legacy build) | `java-ant` | Stack: `java-ant` |
| Scala/sbt | `scala-sbt` | Stack: `scala-sbt` |
| Python -> container -> Kubernetes | `python-k8s` | Stack: `python`; Deploy targets: `kubernetes`; Artifacts: `image` |
| Python -> container | `python-container` | Stack: `python`; Artifacts: `image` |
| Python -> Azure Functions | `python-functions` | Stack: `python`; Deploy targets: `azure-functions` |
| Python -> Azure App Service | `python-appservice` | Stack: `python`; Deploy targets: `azure-app-service` |
| Python package (PyPI) | `python-package` | Stack: `python`; Artifacts: `python-package` |
| Python | `python` | Stack: `python` |
| Go -> container | `go-container` | Stack: `go`; Artifacts: `image` |
| Go | `go` | Stack: `go` |
| Rust | `rust` | Stack: `rust` |
| PHP -> container | `php-container` | Stack: `php`; Artifacts: `image` |
| PHP | `php` | Stack: `php` |
| Ruby | `ruby` | Stack: `ruby` |
| C / C++ (Visual Studio, Windows) | `cpp-msvc` | Stack: `cpp-msvc` |
| C / C++ (CMake) | `cpp-cmake` | Stack: `cpp-cmake` |
| C / C++ | `c-cpp` | Stack: `c-cpp` |
| R | `r` | Stack: `r` |
| Angular SPA -> container -> Kubernetes | `angular-k8s` | Stack: `angular`; Deploy targets: `kubernetes`; Artifacts: `image` |
| Angular SPA -> container -> OpenShift | `angular-openshift` | Stack: `angular`; Deploy targets: `openshift`; Artifacts: `image` |
| Angular SPA -> container (nginx) | `angular-container` | Stack: `angular`; Artifacts: `image` |
| Angular SPA -> IIS | `angular-iis` | Stack: `angular`; Deploy targets: `iis` |
| Angular SPA -> Azure Static Web Apps | `angular-static-web-app` | Stack: `angular`; Deploy targets: `azure-static-web-apps` |
| Angular SPA -> Azure Storage | `angular-azure-storage` | Stack: `angular`; Deploy targets: `azure-storage` |
| Angular SPA -> Azure App Service | `angular-appservice` | Stack: `angular`; Deploy targets: `azure-app-service` |
| Angular library (npm package) | `angular-library` | Stack: `angular`; Artifacts: `npm-package` |
| Angular SPA (static files) | `angular-build` | Stack: `angular` |
| AngularJS 1.x app (legacy) | `angularjs` | Stack: `angularjs` |
| React SPA -> container | `react-container` | Stack: `react`; Artifacts: `image` |
| React SPA -> IIS | `react-iis` | Stack: `react`; Deploy targets: `iis` |
| React SPA -> Azure Static Web Apps | `react-static-web-app` | Stack: `react`; Deploy targets: `azure-static-web-apps` |
| React library (npm package) | `react-library` | Stack: `react`; Artifacts: `npm-package` |
| React SPA (static files) | `react-build` | Stack: `react` |
| Next.js -> container | `nextjs-container` | Stack: `nextjs`; Artifacts: `image` |
| Next.js | `nextjs` | Stack: `nextjs` |
| Gatsby site | `gatsby` | Stack: `gatsby` |
| Vue SPA -> container | `vue-container` | Stack: `vue`; Artifacts: `image` |
| Vue SPA (static files) | `vue-build` | Stack: `vue` |
| Nuxt | `nuxt` | Stack: `nuxt` |
| Svelte / SvelteKit | `svelte` | Stack: `svelte` |
| Electron desktop app | `electron` | Stack: `electron` |
| SharePoint Framework (SPFx) solution | `spfx` | Stack: `spfx` |
| Node -> container -> Kubernetes | `node-k8s` | Stack: `node`; Deploy targets: `kubernetes`; Artifacts: `image` |
| Node -> container -> OpenShift | `node-openshift` | Stack: `node`; Deploy targets: `openshift`; Artifacts: `image` |
| Node -> container | `node-container` | Stack: `node`; Artifacts: `image` |
| Node -> Azure Functions | `node-functions` | Stack: `node`; Deploy targets: `azure-functions` |
| Node -> Azure App Service | `node-appservice` | Stack: `node`; Deploy targets: `azure-app-service` |
| Node package (npm) | `node-package` | Stack: `node`; Artifacts: `npm-package` |
| Node build/publish | `node-build` | Stack: `node` |
| React Native app | `react-native` | Stack: `react-native`; also covers `android`, `ios` |
| Ionic / Capacitor / Cordova app | `hybrid-mobile` | Stack: `hybrid-mobile`; also covers `android`, `ios` |
| Flutter app | `flutter` | Stack: `flutter`; also covers `android`, `ios` |
| Android app | `android` | Stack: `android` |
| iOS / macOS app (macOS runner) | `ios` | Stack: `ios` |
| Database project -> deployment | `database-deploy` | Stack: `database`; Deploy targets: `database` |
| Database project | `database` | Stack: `database` |
| SSIS packages (Windows) | `ssis` | Stack: `ssis` |
| SSRS reports (Windows) | `ssrs` | Stack: `ssrs` |
| SSAS model (Windows) | `ssas` | Stack: `ssas` |
| Power BI reports | `power-bi` | Stack: `power-bi` |
| Azure Data Factory | `azure-data-factory` | Stack: `azure-data-factory` |
| Databricks asset bundle | `databricks` | Stack: `databricks` |
| dbt project | `dbt` | Stack: `dbt` |
| Power Platform solution | `power-platform` | Stack: `power-platform` |
| Salesforce (SFDX) | `salesforce` | Stack: `salesforce` |
| BizTalk (Windows) | `biztalk` | Stack: `biztalk` |
| Delphi (Windows) | `delphi` | Stack: `delphi` |
| Visual Basic 6 (Windows) | `vb6` | Stack: `vb6` |
| Terraform / IaC | `terraform` | Stack: `terraform` |
| Bicep | `bicep` | Stack: `bicep` |
| ARM templates | `arm-templates` | Stack: `arm-templates` |
| AWS CloudFormation / SAM | `cloudformation` | Stack: `cloudformation` |
| AWS CDK | `aws-cdk` | Stack: `aws-cdk` |
| Pulumi | `pulumi` | Stack: `pulumi` |
| Ansible | `ansible` | Stack: `ansible` |
| Chef | `chef` | Stack: `chef` |
| Puppet | `puppet` | Stack: `puppet` |
| Packer (VM images) | `packer` | Stack: `packer` |
| PowerShell module | `powershell-module` | Stack: `powershell` |
| Documentation site (GitLab Pages) | `docs-pages` | Stack: `docs` |
| Helm charts | `helm-chart` | Stack: `helm-charts` |
| Kubernetes / OpenShift manifests | `k8s-manifests` | Stack: `kubernetes-manifests` |
| Container image (Dockerfile only) | `container-image` | Stack: `container` |
| SQL scripts | `sql-scripts` | Stack: `sql-scripts` |
| Scripts only | `scripts` | Stack: `scripts` |
| AZDO YAML template repository | `gitlab-ci-components` | Stack: `azdo-yaml-templates` |
