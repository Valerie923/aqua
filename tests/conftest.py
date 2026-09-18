import os
import tempfile

# Point the app at a throwaway data dir BEFORE app.config is imported.
_tmp = tempfile.mkdtemp(prefix="streamcheck-test-")
os.environ["DATA_DIR"] = _tmp
os.environ.pop("ANTHROPIC_API_KEY", None)
