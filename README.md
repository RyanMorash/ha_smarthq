# SmartHQ

Custom Home Assistant integration for SmartHQ.

## Installation

### HACS

1. In HACS, open the three-dot menu and choose **Custom repositories**.
2. Add `https://github.com/RyanMorash/ha_smarthq` as an integration.
3. Search for **SmartHQ** and download it.
4. Restart Home Assistant.

### Manual

Copy `custom_components/smarthq` into the `custom_components` directory of your Home Assistant configuration and restart Home Assistant.

## Configuration

Open **Settings → Devices & services → Add integration** and select **SmartHQ**. The config flow asks for a username and password.

## What?

This repository contains multiple files. Here is an overview:

File | Purpose | Documentation
-- | -- | --
`.devcontainer.json` | Used for development/testing with Visual Studio Code. | [Documentation](https://code.visualstudio.com/docs/remote/containers)
`.github/dependabot.yml` | Dependency update configuration for Dependabot. | [Documentation](https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/configuration-options-for-the-dependabot.yml-file)
`.github/ISSUE_TEMPLATE/*.yml` | Templates for the issue tracker | [Documentation](https://help.github.com/en/github/building-a-strong-community/configuring-issue-templates-for-your-repository)
`custom_components/smarthq/*` | Integration files, this is where everything happens. | [Documentation](https://developers.home-assistant.io/docs/creating_component_index)
`CONTRIBUTING.md` | Guidelines on how to contribute. | [Documentation](https://help.github.com/en/github/building-a-strong-community/setting-guidelines-for-repository-contributors)
`LICENSE` | The license file for the project. | [Documentation](https://help.github.com/en/github/creating-cloning-and-archiving-repositories/licensing-a-repository)
`README.md` | Overview of the integration, plus installation and configuration instructions. | [Documentation](https://help.github.com/en/github/writing-on-github/basic-writing-and-formatting-syntax)
`requirements_dev.txt` | Python packages used for development/testing this integration (also installs lint tooling via `requirements_lint.txt`). | [Documentation](https://pip.pypa.io/en/stable/user_guide/#requirements-files)
`requirements_lint.txt` | Python packages used to lint this integration (installed by the Lint CI job). | [Documentation](https://pip.pypa.io/en/stable/user_guide/#requirements-files)
`requirements_common.txt` | Python packages common to CI and local dev, installed first so any pip upgrade completes before other dependencies (e.g. a modern pip). | [Documentation](https://pip.pypa.io/en/stable/user_guide/#requirements-files)

## Development

This integration is based on the [integration blueprint](https://github.com/ludeeus/integration_blueprint).

Open the repository in a Visual Studio Code devcontainer, then run `scripts/develop` to start Home Assistant with this integration loaded. Debug logging for `custom_components.smarthq` is set in [`config/configuration.yaml`](./config/configuration.yaml).

## Next steps

These are some next steps you may want to look into:
- Add tests to your integration, [`pytest-homeassistant-custom-component`](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component) can help you get started.
- Add brand images (logo/icon).
- Create your first release.
- Share your integration on the [Home Assistant Forum](https://community.home-assistant.io/).
- Submit your integration to [HACS](https://hacs.xyz/docs/publish/start).
