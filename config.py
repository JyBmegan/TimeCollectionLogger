import subprocess


def _get_keychain(service):
    result = subprocess.run(
        ["security", "find-generic-password", "-s", service, "-w"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Keychain entry '{service}' not found. "
            f"Run: security add-generic-password -a megan -s '{service}' -w 'your-secret'"
        )
    return result.stdout.strip()


def get_notion_api_key():
    return _get_keychain("TimeCollectionLogger_NotionKey")


def get_notion_database_id():
    return _get_keychain("TimeCollectionLogger_NotionDB")
