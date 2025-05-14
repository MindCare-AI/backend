import sys
import pytest

def main():
    # -q for quieter, stop on first fail
    exit_code = pytest.main(["-q", "--maxfail=1", "chatbot/tests/chatbot_accuracy_test.py"])
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
