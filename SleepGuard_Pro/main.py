"""Entry point for SleepGuard Pro."""
from sleepguard.app import SleepGuardApp


def main() -> None:
    app = SleepGuardApp()
    app.mainloop()


if __name__ == "__main__":
    main()
