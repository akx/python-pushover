try:
    import configparser
except ImportError:  # Python 2
    import ConfigParser as configparser

from argparse import ArgumentParser, RawDescriptionHelpFormatter
import os
from pushover import Pushover


def read_config(config_path):
    config_path = os.path.expanduser(config_path)
    config = configparser.RawConfigParser()
    params = {"users": {}, "token": None}
    files = config.read(config_path)
    if not files:
        return params
    for name in config.sections():
        user_config = {
            key: value
            for key, value in config.items(name)
            if key in {"api_token", "device", "user_key"}
        }
        params["users"][name] = user_config
        if name == "main" and user_config.get("api_token"):
            # Legacy config compatibility:
            # Move the "main" user's token, if any, to be the default token
            params["token"] = user_config["api_token"]

    return params


def create_parser():
    parser = ArgumentParser(
        description="Send a message to pushover.",
        formatter_class=RawDescriptionHelpFormatter,
        epilog="""
For more details and bug reports, see: https://github.com/Thibauth/python-pushover""",
    )
    parser.add_argument(
        "--token", help="API token (optional, can be read from config too)"
    )
    parser.add_argument(
        "--user",
        "-u",
        help="user key or section name in the configuration (default 'Default')",
        default="Default",
    )
    parser.add_argument(
        "--device", "-d", help="device key (optional, can be read from config too)",
    )
    parser.add_argument(
        "-c",
        "--config",
        help="configuration file\
                        (default: ~/.pushoverrc)",
        default="~/.pushoverrc",
    )
    parser.add_argument("message", help="message to send")
    parser.add_argument("--url", help="additional url")
    parser.add_argument("--url-title", help="url title")
    parser.add_argument("--title", "-t", help="message title")
    parser.add_argument(
        "--priority", "-p", help="notification priority (-1, 0, 1 or 2)", type=int
    )
    parser.add_argument(
        "--retry",
        "-r",
        help="resend interval in seconds (required for priority 2)",
        type=int,
    )
    parser.add_argument(
        "--expire",
        "-e",
        help="expiration time in seconds (required for priority 2)",
        type=int,
    )
    parser.add_argument(
        "--version",
        "-v",
        action="version",
        help="output version information and exit",
        version="""
%(prog)s 1.0
Copyright (C) 2013-2018 Thibaut Horel <thibaut.horel@gmail.com>
License GPLv3+: GNU GPL version 3 or later <http://gnu.org/licenses/gpl.html>.
This is free software: you are free to change and redistribute it.
There is NO WARRANTY, to the extent permitted by law.""",
    )
    return parser


def update_args_with_configuration(args):
    params = read_config(args.config)
    if args.priority == 2 and (args.retry is None or args.expire is None):
        raise ValueError("priority of 2 requires expire and retry")
    user_info = params["users"].get(args.user)
    args.token = args.token or params["token"]
    args.user_key = args.user
    args.device = None
    if user_info:
        args.user_key = user_info.get("user_key", args.user_key)
        args.device = user_info.get("device", args.device)
        args.token = user_info.get("api_token", args.token)
    if not args.user_key:
        raise ValueError("User key missing!")
    if not args.token:
        raise ValueError("API token missing!")


def main():
    parser = create_parser()

    args = parser.parse_args()
    update_args_with_configuration(args)

    Pushover(args.token).message(
        args.user_key,
        args.message,
        device=args.device,
        title=args.title,
        priority=args.priority,
        url=args.url,
        url_title=args.url_title,
        timestamp=True,
        retry=args.retry,
        expire=args.expire,
    )


if __name__ == "__main__":
    main()
