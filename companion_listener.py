import http.server
import json
import time
import sys

from core import CptError

HOST = '127.0.0.1'
PORT = 1327

# Seconds to wait for each subsequent problem of a multi-problem batch. CC sends
# a batch's problems within milliseconds of each other, so a stall this long
# means the batch was truncated (tab closed, extension hiccup); returning what
# arrived is better than blocking the tool indefinitely.
BATCH_TIMEOUT = 10.0

# Fields cptool relies on from every Competitive Companion payload.
REQUIRED_FIELDS = ('name', 'group', 'url', 'tests', 'batch')


class _CompetitiveCompanionHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body           = self.rfile.read(content_length)
            problem        = json.loads(body)
            _validate(problem)               # reject invalid payloads with 400
            self.server.received = problem
            self.send_response(200)
        except Exception as e:
            print(f'Warning: rejected Competitive Companion payload: {e}',
                  file=sys.stderr)
            self.send_response(400)
        finally:
            self.end_headers()

    def log_message(self, format, *args):
        pass


class _CompanionServer(http.server.HTTPServer):
    # Avoid "Address already in use" when relaunching shortly after a previous run.
    allow_reuse_address = True
    timed_out = False

    def handle_timeout(self):
        # Called by handle_request() when self.timeout elapses with no request.
        self.timed_out = True


def _validate(problem: dict) -> None:
    missing = [field for field in REQUIRED_FIELDS if field not in problem]
    if missing:
        raise CptError(
            f"Competitive Companion payload missing field(s): {', '.join(missing)}"
        )
    # name/group/url become directory segments, so they must be usable strings.
    for field in ('name', 'group', 'url'):
        value = problem[field]
        if not isinstance(value, str) or not value.strip():
            raise CptError(f"Competitive Companion payload has an empty or non-string '{field}'.")
    # batch.size drives how many problems a batch collects; it must be a positive
    # integer (and not a bool, which is an int subclass in Python).
    batch = problem['batch']
    size  = batch.get('size') if isinstance(batch, dict) else None
    if not isinstance(size, int) or isinstance(size, bool) or size < 1:
        raise CptError("Competitive Companion payload has a malformed 'batch' (size must be a positive integer).")


def _receive(server: _CompanionServer, *, timeout: float | None) -> dict | None:
    """Wait for one valid problem and return it, or return None on timeout.

    A POST that arrives but fails _validate (gets a 400 response) is skipped
    and we keep waiting — a single bad payload doesn't abort the whole run.
    `timeout=None` blocks indefinitely (used for the first problem in a batch).
    """
    server.timeout = timeout
    while True:
        server.received  = None
        server.timed_out = False
        server.handle_request()
        if server.received is not None:
            return server.received
        if server.timed_out:
            return None
        # A request arrived but was rejected (400 response); keep waiting.


def _warn_partial_batch(received_count: int, expected_count: int) -> None:
    print(
        f'Warning: received only {received_count} of {expected_count} '
        f'problems before the batch stalled; continuing with those.',
        file=sys.stderr,
    )


def collect_batch() -> list[dict]:
    """Listen for and return one complete batch of problems.

    Competitive Companion tags every problem with batch.id and batch.size. We
    pin the id of the first problem so that a stray problem from a concurrent
    parse action can't be mixed into this batch. Subsequent problems are
    awaited with BATCH_TIMEOUT so a truncated batch returns what it has rather
    than blocking forever.
    """
    try:
        server = _CompanionServer((HOST, PORT), _CompetitiveCompanionHandler)
    except OSError as e:
        raise CptError(
            f"Could not start the Competitive Companion listener on "
            f"{HOST}:{PORT} ({e}). Is another instance already running?"
        )
    try:
        first_problem = _receive(server, timeout=None)   # block until first problem
        # timeout=None never fires handle_timeout, so first_problem can't be None.
        # The guard below is purely defensive for type-checker clarity.
        if first_problem is None:
            raise CptError('No valid problem received from Competitive Companion.')

        batch_id = first_problem['batch'].get('id')
        expected_batch_size = first_problem['batch']['size']
        batch_deadline = time.monotonic() + BATCH_TIMEOUT
        problems = [first_problem]

        while len(problems) < expected_batch_size:
            time_left = batch_deadline - time.monotonic()
            if time_left <= 0:
                _warn_partial_batch(len(problems), expected_batch_size)
                break

            next_problem = _receive(server, timeout=time_left)
            if next_problem is None:
                _warn_partial_batch(len(problems), expected_batch_size)
                break
            if next_problem['batch'].get('id') != batch_id:
                print('Warning: ignoring a problem from a different batch.',
                      file=sys.stderr)
                continue
            problems.append(next_problem)

        return problems
    finally:
        server.server_close()
