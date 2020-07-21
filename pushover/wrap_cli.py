import shlex
import subprocess
import sys
import tempfile
from itertools import count

from pushover.cli import (
    create_parser,
    update_args_with_configuration,
    send_message_from_args,
)


def run_process(args, stdout_file, stderr_file):
    # Py2/3 compat; `sys.stdin.buffer` only exists on Py3 and is for binary IO
    stdin = getattr(sys.stdin, "buffer", sys.stdin)
    proc = subprocess.Popen(
        args=shlex.split(args.command),
        shell=True,
        stdin=stdin,
        stdout=stdout_file,
        stderr=stderr_file,
    )
    message = None
    try:
        proc.wait(timeout=args.timeout)
    except subprocess.TimeoutExpired:
        message = "Reached timeout {} and was killed".format(args.timeout)
    except Exception as exc:
        message = "Caught exception {} and was killed".format(exc)
    else:
        if proc.returncode != 0 or args.always:
            message = "Exited with code {}".format(proc.returncode)
    try:
        # This is safe to do if the process is already dead.
        proc.kill()
    except Exception:
        pass
    return (proc, message)


def read_stream_suffix(stream_file, suffix_size=1024):
    stream_file.flush()
    stream_size = stream_file.tell()
    stream_file.seek(max(stream_size - suffix_size, 0))
    # errors="ignore" should be able to recover from starting to read within an UTF-8 character.
    stream_suffix = stream_file.read().decode("UTF-8", errors="ignore")
    return stream_suffix, stream_size


def format_final_message(error_message, stderr_file, stdout_file):
    # "Messages are currently limited to 1024 4-byte UTF-8 characters", so we try
    # to balance the message to show the interesting bits (tails of both streams).

    # Gather up about a kilobyte of both streams, interpreting as UTF-8 (for sanity's sake).
    stdout_message, stdout_size = read_stream_suffix(stdout_file)
    stderr_message, stderr_size = read_stream_suffix(stderr_file)
    stdout_offset = 0
    stderr_offset = 0

    for iteration in count(0):
        final_message = "{}\n".format(error_message or "")
        if stdout_message:
            final_message += "Stdout ({}b):\n{}\n".format(
                stdout_size, stdout_message[stdout_offset:]
            )
        if stderr_message:
            final_message += "Stderr ({}b):\n{}\n".format(
                stderr_size, stderr_message[stderr_offset:]
            )
        final_message = final_message.strip()
        # If the message, encoded as UTF-8, is short enough, we're done here.
        if len(final_message.encode("utf-8")) < 1020:
            return final_message
        # If we need to shorten the message, snip out 2% of the remaining lengths in a round-robin manner.
        if iteration % 2 == 0:
            stdout_offset += int(len(stdout_message) / 50)
        else:
            stderr_offset += int(len(stderr_message) / 50)


def wrap_main():
    parser = create_parser()
    parser.add_argument("--command", required=True, help="the command to run")
    parser.add_argument(
        "--always",
        action="store_true",
        help="send a message even if the command succeeds",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="don't print the message sent",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="optional timeout for the command, in seconds",
    )
    parser.add_argument(
        "--pass-returncode",
        action="store_true",
        default=True,
        help="pass through the subprocess's return code as this program's (default yes)",
    )
    parser.add_argument(
        "--no-pass-returncode",
        action="store_false",
        default=True,
        help="return 0 even if the subprocess didn't (not the default)",
    )
    args = parser.parse_args()
    update_args_with_configuration(args)
    with tempfile.NamedTemporaryFile(
        mode="wb+", prefix="pushover-stdout-"
    ) as stdout_file, tempfile.NamedTemporaryFile(
        mode="wb+", prefix="pushover-stderr-"
    ) as stderr_file:
        proc, error_message = run_process(args, stdout_file, stderr_file)
        if error_message:
            try:
                args.message = format_final_message(
                    error_message, stderr_file, stdout_file
                )
            except Exception as exc:
                args.message = "{}\n(failed formatting error: {})".format(
                    error_message, exc
                )
            if not args.quiet:
                print(args.message)
            send_message_from_args(args)
    if args.pass_returncode:
        sys.exit(proc.returncode)


if __name__ == "__main__":
    wrap_main()
