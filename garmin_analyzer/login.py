"""Interactive first-time login: python -m garmin_analyzer.login"""

from .garmin_client import has_saved_tokens, interactive_login


def main() -> None:
    if has_saved_tokens():
        print("כבר קיים session שמור. מתחבר מחדש בכל זאת...")
    interactive_login()


if __name__ == "__main__":
    main()
