import sys
from pathlib import Path

# Always add the project root to sys.path so `import tools` works
# regardless of which pytest binary or working directory is used.
sys.path.insert(0, str(Path(__file__).parent.parent))
