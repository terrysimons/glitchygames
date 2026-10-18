"""PyInstaller hook for aisuite (used by Bitmappy's AI sprite generation).

aisuite discovers its providers by globbing ``aisuite/providers/*_provider.py`` on disk
(``ProviderFactory.get_supported_providers``) and imports them by name at runtime. A frozen app
stores modules compiled inside PyInstaller's archive, so the glob finds nothing and every request
fails with "Supported providers: set()". This hook bundles the chosen provider modules (for the
dynamic import) and their source files (for the glob).

Only the providers Bitmappy is meant to use are bundled, rather than all of aisuite's, so the
binary does not pull in every vendor SDK; any other provider fails with aisuite's clear
"not supported" error.
"""

from PyInstaller.utils.hooks import collect_data_files

# Provider keys as used in AI_MODEL ("anthropic:claude-...", "openai:...", "ollama:...")
SUPPORTED_AI_PROVIDERS = ['anthropic', 'openai', 'ollama']

hiddenimports = [f'aisuite.providers.{provider}_provider' for provider in SUPPORTED_AI_PROVIDERS]
datas = collect_data_files(
    'aisuite',
    include_py_files=True,
    includes=[f'providers/{provider}_provider.py' for provider in SUPPORTED_AI_PROVIDERS],
)
