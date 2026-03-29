import traceback
import sys
try:
    import backend.main
    import bot.main
    print("Imports OK")
except Exception:
    traceback.print_exc()
    sys.exit(1)
