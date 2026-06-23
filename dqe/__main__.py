"""Enable ``python -m dqe`` as an alias for the CLI."""
from dqe.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
