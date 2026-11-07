"""Resume content shim (JSA-077, 2026-11-02): the candidate's resume content is personal data and lives in
config/resume_content.py (falls back to config/resume_content.example.py). Scripts keep `import content as C`."""
import importlib.util
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'config'))
import jsa_profile  # noqa: E402
_spec = importlib.util.spec_from_file_location('resume_content', jsa_profile.data_file('resume_content.py', 'JSA_RESUME_CONTENT'))
_m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_m)
globals().update({k: v for k, v in vars(_m).items() if not k.startswith('_')})
