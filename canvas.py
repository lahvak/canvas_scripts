"""
A module for interacting with Instructure Canvas

Global parameters (most can also be changed on individual function calls):
    BASE_URL: string, containing the base url of canvas server
    TOKEN: string, containing the user access token.
    THIS_YEAR: current year, for making class schedules
"""
import requests
import arrow
import markdown
from os.path import expanduser, getsize, basename
from requests.exceptions import HTTPError

HAS_PANDOC = True
try:
    import pypandoc
except ImportError:
    HAS_PANDOC = False

BASE_URL = "https://svsu.instructure.com/"
TOKEN = 'An invalid token.  Redefine with your own'
THIS_YEAR = int(arrow.now().format('YYYY'))


def read_access_token(file='~/.canvas/access_token'):
    "Read access token if available"
    global TOKEN
    try:
        with open(expanduser(file), 'r') as f:
            TOKEN = f.read().rstrip('\n')
    except Exception as err:
        print("Could not read access token due to the following error: ",
              repr(err))


def check_headers(headers):
    """
    Make sure headers contain authorization info.
    """
    if headers is None or "Authorization" not in headers:
        raise ValueError("Headers must contain authorization info.")


def add_item_to_possible_list(item_or_list, item):
    """
    If `item_or_list` is not list, returns `[item_or_list, item]`.
    Otherwise add `item` to `item_or_list` and returns that.
    """

    if isinstance(item_or_list, list):
        return item_or_list + [item]

    return [item_or_list, item]


class RequestBase(object):
    def __init__(self, locashun, base=None, access_token=None):
        self.base = BASE_URL if base is None else base
        self.token = TOKEN if access_token is None else access_token
        self.locashun = locashun
        self.stuff = {"headers": {"Authorization": f"Bearer {self.token}"}}

    def URL(self):
        locashun = self.locashun
        if locashun[0] == "/":
            locashun = locashun[1:]

        if self.base[-1] == "/":
            sep = ""
        else:
            sep = "/"

        return self.base + sep + locashun

    def base_request_add_to_dict(self, which_stuff, key, value, overwrite):
        if which_stuff not in self.stuff:
            self.stuff[which_stuff] = {key: value}
        elif not overwrite and key in self.stuff[which_stuff]:
            add_item_to_possible_list(self.stuff[which_stuff][key], value)
        else:
            self.stuff[which_stuff][key] = value

    def base_request_add_optional_to_dict(self, which_stuff, key, value,
                                          overwrite):
        if value is not None:
            self.base_request_add_to_dict(which_stuff, key, value, overwrite)

    def base_request_add_dict_to_dict(self, which_stuff, hash):
        if (
                which_stuff not in self.stuff
                or not isinstance(self.stuff[which_stuff], dict)
                ):
            self.stuff[which_stuff] = hash.copy()
        else:
            self.stuff[which_stuff].update(hash)


class Request(RequestBase):
    def __init__(self, function, locashun, base=None, access_token=None):
        super().__init__(locashun, base, access_token)
        self.function = function
        self.stuff["params"] = dict()

    def add_param(self, key, value, overwrite=False):
        self.base_request_add_to_dict("params", key, value, overwrite)

    def add_optional_param(self, key, value, overwrite=False):
        self.base_request_add_optional_to_dict("params", key, value, overwrite)

    def add_param_dict(self, hash):
        self.base_request_add_dict_to_dict("params", hash)

    def submit(self):
        return self.function(self.URL(),
                             params=self.stuff["params"],
                             headers=self.stuff["headers"])


class RequestWithData(Request):
    def __init__(self, function, locashun, base=None, access_token=None):
        super().__init__(function, locashun, base, access_token)
        self.stuff["data"] = dict()

    def add_data(self, key, value, overwrite=False):
        self.base_request_add_to_dict("data", key, value, overwrite)

    def add_optional_data(self, key, value, overwrite=False):
        self.base_request_add_optional_to_dict("data", key, value, overwrite)

    def add_data_dict(self, hash):
        self.base_request_add_dict_to_dict("data", hash)

    def submit(self):
        return self.function(self.URL(), data=self.stuff["data"],
                             params=self.stuff["params"],
                             headers=self.stuff["headers"])


class RequestOrderedData(Request):
    def __init__(self, function, locashun, base=None, access_token=None):
        super().__init__(function, locashun, base, access_token)
        self.stuff["data"] = []

    def add_data(self, key, value):
        self.stuff['data'] += [(key, value)]

    def add_optional_data(self, key, value):
        if value is not None:
            self.stuff['data'] += [(key, value)]

    def add_data_dict(self, hash):
        self.stuff['data'] += [(key, value) for key, value in hash.items()]

    def submit(self):
        return self.function(self.URL(), data=self.stuff["data"],
                             params=self.stuff["params"],
                             headers=self.stuff["headers"])



def get_all_pages(orig_url, params=None, headers=None):
    """
    Auxiliary function that uses the 'next' links returned from the server to
    request additional pages and combine them together into one json response.
    Parameters:
        orig_url: the url for the original request
        params: a dict with the parameters for the original request
        headers: Headers for the requests.  Must contain authorization info.
    Returns:
        A combined list of json results returned in all pages.
    Warning:
        Does not handle failure in any way! Make sure you don't kill your pets
        by accident.
    """
    url = orig_url
    json = []

    check_headers(headers)

    if params is None:
        params = {}
    while True:
        resp = requests.get(url, params=params, headers=headers)
        json += resp.json()
        if 'next' not in resp.links:
            return json
        url = resp.links['next']['url']
        params = {}


def get_to_json(url, params=None, headers=None):
    """
    Makes a GET request to a given url, and return json from the server.

    `headers` must contain authorization info.

    Returns json code from the response, or json with error code if there is
    an HTTP error.
    """

    check_headers(headers)

    try:
        resp = requests.get(url, params=params, headers=headers)
        resp.raise_for_status()
    except HTTPError as err:
        return {'Error': err.response.status_code, 'URL': resp.url}

    return resp.json()


def delete_to_json(url, params=None, headers=None):
    """
    Makes a DELETE request to a given url, and return json from the server.

    `headers` must contain authorization info.

    Returns json code from the response, or json with error code if there is
    an HTTP error.
    """

    check_headers(headers)

    try:
        resp = requests.delete(url, params=params, headers=headers)
        resp.raise_for_status()
    except HTTPError as err:
        return {'Error': err.response.status_code, 'URL': resp.url}

    return resp.json()


def put_to_json(url, params=None, data=None, headers=None):
    """
    Makes a GET request to a given url, and return json from the server.

    `headers` must contain authorization info.

    Returns json code from the response, or json with error code if there is
    an HTTP error.
    """

    check_headers(headers)

    try:
        resp = requests.put(url, params=params, data=data, headers=headers)
        resp.raise_for_status()
    except HTTPError as err:
        return {'Error': err.response.status_code, 'URL': resp.url}

    return resp.json()


def post_to_json(url, params=None, data=None, headers=None):
    """
    Makes a POST request to a given url, and return json from the server.

    `headers` must contain authorization info.

    Returns json code from the response, or json with error code if there is
    an HTTP error.
    """

    check_headers(headers)

    try:
        resp = requests.post(url, params=params, data=data, headers=headers)
        resp.raise_for_status()
    except HTTPError as err:
        return {'Error': err.response.status_code, 'URL': resp.url}

    return resp.json()


def upload_file(url, params=None, data=None, headers=None):
    """
    Initiates a file upload to a given url. The `data` parameter must have a
    key called `local_file`, containing the local path to the uploaded file.

    `headers` must contain authorization info.

    Returns a combined json of the two requests, with keys:
        'init' from upload init request
        'upload' from the actual upload
    """

    check_headers(headers)

    if 'local_file' not in data:
        raise ValueError("No path to local file given.")

    local_file = data.pop('local_file')

    # TODO: should check that it exists

    resp = requests.post(url, params=params, data=data, headers=headers)

    resp.raise_for_status()

    json1 = resp.json()

    upload_url = json1["upload_url"]
    upload_params = json1["upload_params"]

    with open(local_file, 'rb') as file:
        resp = requests.post(
            upload_url, data=upload_params, files={'file': file}
        )

    resp.raise_for_status()

    json2 = resp.json()

    return {'init': json1, 'upload': json2}


def progress(prog_url, headers=None):
    """
    Iterator that repeatedly checks progress from the given url.  It yields the
    json results of the progress query.  It stops when workflow state is no
    longer queued nor running.  The `headers` must contain authorization info.
    """

    check_headers(headers)

    while True:
        resp = requests.get(prog_url, headers=headers)
        resp.raise_for_status()
        json = resp.json()
        yield json
        status = json['workflow_state']
        if status != 'queued' and status != 'running':
            break


def create_calendar_event(course, title, description, start_at, end_at,
                          base=None, access_token=None):
    """
    Creates a calendar event.
    Parameters:
        course: course id, string or int
        title: string, event title
        description: string, detailed event description
        start_at: starting time, in YYYY-MM-DDTHH:MMZZ format
        end_at: ending time, in YYYY-MM-DDTHH:MMZZ format
    Returns: json from server
    """

    req = RequestWithData(
        post_to_json,
        'api/v1/calendar_events.json',
        base,
        access_token
    )
    req.add_data('calendar_event[context_code]', f'course_{course}')
    req.add_data('calendar_event[title]', title)
    req.add_data('calendar_event[description]', description)
    req.add_data('calendar_event[start_at]', start_at)
    req.add_data('calendar_event[end_at]', end_at)

    return req.submit()


def list_calendar_events_between_dates(course, start_date, end_date, base=None,
                                       access_token=None):
    """Lists all events in a given course between two dates.
    Parameters:
        course: course ID
        start_date: start date in YYYY-MM-DD format
        end_date: end date in YYYY-MM-DD format
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one
    Returns a list of json descriptions of events.
    """

    req = Request(
        get_all_pages, 'api/v1/calendar_events.json', base, access_token
    )
    req.add_data('type', 'event')
    req.add_data('start_date', start_date)
    req.add_data('end_date', end_date)
    req.add_data('context_codes[]', f'course_{course}')

    return req.submit()


def list_calendar_events_all(course, base=None, access_token=None):
    """Lists all events in a given course.
    Parameters:
        course: course ID
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one
    """

    req = Request(
        get_all_pages, 'api/v1/calendar_events.json', base, access_token
    )
    req.add_data('type', 'event')
    req.add_data('all_events', True)
    req.add_data('context_codes[]', f'course_{course}')

    return req.submit()


def delete_event(event_id, reason='no reason', base=None, access_token=None):
    """Deletes an event, specified by 'event_id'. Returns the event."""

    req = Request(
        delete_to_json, f'api/v1/calendar_events/{event_id}',
        base, access_token
    )
    req.add_data('cancel_reason', reason)

    return req.submit()


# TODO: move these to canvas_utils module

def class_span(start, length):
    """Returns class starting and ending time in isoformat.  To be used with
    `calendar_event_data`. Parameters:
        start: an arrow object describing class starting time
        length: length of class in minutes
    """
    return start.isoformat(), start.replace(minutes=length).isoformat()


def firstclass(month, day, hour, minute, year=THIS_YEAR):
    """
    A convenience function creating an arrow object for the first class
    in the semester
    """
    return arrow.Arrow(year, month, day, hour, minute, 0, 0, 'local')


def create_events_from_list(course, event_list, start, length, base=None,
                            access_token=None):
    """
    Creates a series of events for a MW or TR class. Parameters:
        course: a course id, string or int
        list: a list of events.  A list of pairs, the first item in each is a
            title, the second is a description. An empty string for title will
            skip that day.
        start: an arrow object describing the starting time of the first class.
            Must be Monday or Tuesday!
        length: int, length of class in minutes
    """
    classtime = start
    for i, event in enumerate(event_list):
        if event[0] != "":
            create_calendar_event(
                course, event[0], event[1], *class_span(classtime, length),
                base, access_token
            )
        classtime = classtime.shift(days=2 if i % 2 == 0 else 5)


def convert_markdown(body, use_pandoc):
    """
    Convert markdown string `body` to html. Use pandoc for conversion if
    `use_pandoc` is true and pandoc is available.
    """

    if use_pandoc and not HAS_PANDOC:
        print("Warning: pypandoc not available! Trying builtin converter.")
        print("Install pypandoc module to get rid of this error.")
        use_pandoc = False

    if use_pandoc:
        return pypandoc.convert_text(body, "html", format="md",
                                     extra_args=["--mathml"])
    else:
        return markdown.markdown(body, extensions=['extra'])


def upload_syllabus_from_markdown(course, markdown_body, access_token=None,
                                  use_pandoc=False, base=None):
    """
    Uploads syllabus body to a given course.
    Parameters:
        course: a course ID, int or string
        markdown_body: the body of syllabus in markdown
        use_pandoc: use Pandoc to convert markdown when available
        access_token: access token
        base: base url of canvas server
    """

    req = RequestWithData(
        put_to_json, f'api/v1/courses/{course}', base, access_token
    )
    req.add_data('course[syllabus_body]',
                 convert_markdown(markdown_body, use_pandoc))

    req.submit()


def post_announcement_from_markdown(
        course, title, markdown_body, use_pandoc=False,
        access_token=None, base=None):
    """
    Post an announcement to a given course
    Parameters:
        course: a course ID, int or string
        title: the title of the announcement
        markdown_body: the body of the announcement in markdown
        use_pandoc: use Pandoc to convert markdown when available
        access_token: access token
        base: base url of canvas server
    """

    req = RequestWithData(
        post_to_json, f'api/v1/courses/{course}/discussion_topics',
        base, access_token
    )
    req.add_data('title', title)
    req.add_data('message', convert_markdown(markdown_body, use_pandoc))
    req.add_data('is_announcement', '1')

    return req.submit()


def post_group_announcement_from_markdown(
        group, title, markdown_body, use_pandoc=False,
        access_token=None, base=None):
    """
    Post an announcement to a given group
    Parameters:
        group: a group ID, int or string
        title: the title of the announcement
        markdown_body: the body of the announcement in markdown
        use_pandoc: use Pandoc to convert markdown when available
        access_token: access token
        base: base url of canvas server
    """

    req = RequestWithData(
        post_to_json, f'api/v1/groups/{group}/discussion_topics',
        base, access_token
    )
    req.add_data('title', title)
    req.add_data('message', convert_markdown(markdown_body, use_pandoc))
    req.add_data('is_announcement', '1')

    return req.submit()


def create_discussion(
        course, title, markdown_message, discussion_type="threaded",
        position_after=None,
        published=True, allow_rating=False, sort_by_rating=False,
        only_graders_can_rate=False,
        podcast_enabled=False, podcast_student_posts=False,
        require_initial_post=False, pinned=False, group=None,
        use_pandoc=False,
        access_token=None, base=None):
    """
    Post a new discussion in a given course
    Parameters:
        course: a course ID, int or string
        title: the title of the discussion
        markdown_message: the message in markdown
        discussion_type: threaded or side_comment
        position_after: optional id of other discussion
        published: should it be published
        allow_rating: can post be rated
        sort_by_rating: sort posts by rating
        only_graders_can_rate: if true, only graders can rate (duh)
        podcast_enabled: is there a podcast for the discussion
        podcast_student_posts: include student posts in podcast
        require_initial_post: do students have to post before commenting on
            other posts
        pinned: should the discussion be pinned
        group: if set, the discussion will become a group discussion in a group
            with this id
        use_pandoc: use Pandoc to convert markdown when available
        access_token: access token
        base: base url of canvas server
    """

    req = RequestWithData(
        post_to_json, f'api/v1/courses/{course}/discussion_topics',
        base, access_token
    )
    req.add_data('title', title)
    req.add_data('message', convert_markdown(markdown_message, use_pandoc))
    req.add_data('is_announcement', '0')
    req.add_data('discussion_type', discussion_type)
    req.add_data('published', published)
    req.add_data('allow_rating', allow_rating)
    req.add_data('sort_by_rating', sort_by_rating)
    req.add_data('only_graders_can_rate', only_graders_can_rate)
    req.add_data('podcast_enabled', podcast_enabled)
    req.add_data('podcast_has_student_posts', podcast_student_posts)
    req.add_data('require_initial_post', require_initial_post)
    req.add_data('pinned', pinned)
    req.add_data_optional('group', group)
    req.add_data_optional('position_after', position_after)

    return req.submit()


def create_page_from_markdown(course, title, markdown_body, published=True,
                              use_pandoc=False, access_token=None, base=None):
    """
    Creates a wiki page in a given course
    Parameters:
        course: a course ID, int or string
        title: the title of the page
        markdown_body: the body of page in markdown
        published: if the page should be published
        use_pandoc: use Pandoc to convert markdown when available
        access_token: access token
        base: base url of canvas server
    """

    req = RequestWithData(
        post_to_json, f'api/v1/courses/{course}/pages', base, access_token
    )
    req.add_data('wiki_page[title]', title)
    req.add_data('wiki_page[body]',
                 convert_markdown(markdown_body, use_pandoc))
    req.add_data('wiki_page[published]', '1' if published else '0')

    return req.submit()


# The following function was provided by Mark A. Lilly (marqpdx):

def update_page_from_markdown(
        course, title, markdown_body, url, published=True,
        use_pandoc=False, access_token=None, base=None):
    """
    updates a wiki page in a given course
    Parameters:
        course: a course ID, int or string
        title: the title of the page
        markdown_body: the body of page in markdown
        url: the url of this page in the current course
        published: if the page should be published
        use_pandoc: use Pandoc to convert markdown when available
        access_token: access token
        base: base url of canvas server
    """

    req = RequestWithData(
        put_to_json, f'api/v1/courses/{course}/pages/{url}', base, access_token
    )
    req.add_data('wiki_page[title]', title)
    req.add_data('wiki_page[body]',
                 convert_markdown(markdown_body, use_pandoc))
    req.add_data('wiki_page[published]', '1' if published else '0')

    return req.submit()


def get_assignment_groups(course, access_token=None, base=None):
    """
    Gets a list of all assignment groups for a course.
    Parameters:
        course: a course ID, int or string
        access_token: access token
        base: base url of canvas server
    """

    req = Request(
        get_all_pages, f'api/v1/courses/{course}/assignment_groups',
        base, access_token
    )
    req.add_param('include[]', 'assignments')

    return req.submit()


def create_assignment_group(course, name, position=None, group_weight=0,
                            access_token=None, base=None):
    """
    Create an assignment group in the course.
    Parameters:
        course: a course ID, int or string
        name: the name of the group
        position: position of the group on the group list
        group_weight: relative weight of the group in grading, percent
        access_token: access token
        base: base url of canvas server

    Currently does not allow setting grading rules. (TODO)
    """

    req = RequestWithData(
        post_to_json, f'api/v1/courses/{course}/assignment_groups',
        base, access_token
    )
    req.add_data('name', name)
    req.add_data('group_weight', group_weight)
    req.add_optional_data('position', position)

    return req.submit()


def delete_assignment_group(course, group_id, move_assignments_to=None,
                            access_token=None, base=None):
    """
    Create an assignment group in the course.
    Parameters:
        course: a course ID, int or string
        group_id: the id of the group, int or string
        move_assignments_to: id of a group to move assignments to, if None,
            the assignments will be deleted
        access_token: access token
        base: base url of canvas server
    """

    req = Request(
        delete_to_json,
        f'api/v1/courses/{course}/assignment_groups/{group_id}',
        base, access_token
    )
    req.add_optional_param('move_assignments_to', move_assignments_to)

    return req.submit()


def create_assignment(course, name, markdown_description, points, due_at,
                      group_id, submission_types="on_paper",
                      allowed_extensions=None, peer_reviews=False,
                      auto_peer_reviews=False, ext_tool_url=None,
                      ext_tool_new_tab=False,
                      use_pandoc=True,
                      access_token=None, base=None):
    """
    Creates a simple assignment in the given course.
    Parameters:
        course: a course ID, int or string
        name: the name of the assignment
        markdown_description: description of the assignment, in markdown
        points: max number of points for the assignment
        due_at: due date for the assignment, in YYYY-MM-DDTHH:MM:SS
        group_id: assignment group to place the assignment into
        submission_types: how should it be submitted. Options are
            "online_quiz", "none", "on_paper", "discussion_topic",
            "external_tool", "online_upload", "online_text_entry",
            "online_url", "media_recording"
        allowed_extensions: if submission_types contains "online_upload", list
            of allowed file extensions
        peer_reviews: should the assignment be peer reviwed
        auto_peer_reviews: assign reviewers automatically
        ext_tool_url: url of external tool, is submission_types contains
            "external_tool".
        ext_tool_new_tab: Boolean, should external tool open in a new tab.
        use_pandoc: use Pandoc for markdown conversion, if installed.
        access_token: access token
        base: base url of canvas server
    """

    # The Canvas API documentation is wrong or at least misleading, submitting
    # a hash for external_tool_assignment_tag causes internal server error. The
    # fields have to he sent separately.

    req = RequestWithData(
        post_to_json, f'api/v1/courses/{course}/assignments',
        base, access_token
    )
    req.add_data('assignment[name]', name)
    req.add_data('assignment[description]',
                 convert_markdown(markdown_description, use_pandoc))
    req.add_data('assignment[submission_types]', submission_types)
    req.add_data('assignment[points_possible]',  points)
    req.add_data('assignment[due_at]', due_at)
    req.add_data('assignment[assignment_group_id]',  group_id)
    req.add_data('assignment[published]', 1)
    req.add_data('assignment[peer_reviews]', peer_reviews)
    req.add_data('assignment[automatic_peer_rewiews]', auto_peer_reviews)
    req.add_optional_data('assignment[allowed_extensions]', allowed_extensions)
    if ext_tool_url is not None:
        req.add_data(
            'assignment[external_tool_tag_attributes][url]', ext_tool_url
        )
        req.add_data(
            'assignment[external_tool_tag_attributes][new_tab]',
            ext_tool_new_tab
        )

    return req.submit()


def course_settings_set(course, settings, access_token=None, base=None):
    """
    Set settings in a course.
    Parameters:
        course: the course id
        settings: a dict with course settings to change. Keys should be the
            parts inside the square brackets of the parameter names for the
            "Update a Course" API request
    """

    req = RequestWithData(
        put_to_json, f'api/v1/courses/{course}', base, access_token
    )
    for k, v in settings.items():
        req.add_data(f"course[{k}]", v)

    return req.submit()


def create_redirect_tool(
        course, text, url, new_tab=False, default=True,
        access_token=None, base=None):
    """
    Create a redirect tool for course navigation.
    Parameters:
        course: the course id
        text: the text that will be displayed in the navigation
        url: the redirection url
        new_tab: should it open in a new tab?
        default: should the tool be enabled by default
        access_token: access token
        base: base url of canvas server
    """

    req = RequestWithData(
        post_to_json, f'api/v1/courses/{course}/external_tools',
        base, access_token
    )
    req.add_data_dict(
        {
            'name': 'Redirect to ' + text,
            'privacy_level': 'Anonymous',
            'consumer_key': 'N/A',
            'shared_secret': 'hjkl',
            'url': 'https://www.edu-apps.org/redirect',
            'text': text,
            'custom_fields[url]': url,
            'custom_fields[new_tab]': (1 if new_tab else 0),
            'not_selectable': True,
            'course_navigation[enabled]': True,
            'course_navigation[text]': text,
            'course_navigation[default]': default,
            'description': "Redirects to " + url
        })

    return req.submit()


def list_files(course, pattern, folder=None,
               access_token=None, base=None):
    """
    Lists files matching pattern
    Parameters:
        course: the course id
        pattern: the pattern to match
        folder: currently unused
        access_token: access token
        base: base url of canvas server
    """

    req = Request(
        get_all_pages, f'api/v1/courses/{course}/files', base, access_token
    )
    req.add_param('search_term', pattern)

    return req.submit()


def upload_file_to_course(course, local_file, upload_path, remote_name=None,
                          content_type=None, overwrite=False,
                          access_token=None, base=None):
    """
    Upload a file to the course 'files'.
    Parameters:
        course: the course id
        local_file: the local path to the file.  The file must exist, and not
            be huge
        upload_path: the remote directory the file goes to.  It will be created
            if it does not exist
        remote_name: the file name to use on the server. When unspecified, it
            will be extracted from `local_file`
        content_type: mailcap style content type.  Will be inferred from the
            file extension if unspecified
        overwrite: if True, overwrite existing file.  Otherwise upload file
            under a modified name
        access_token: access token
        base: base url of canvas server
    """

    if remote_name is None:
        remote_name = basename(local_file)

    req = RequestWithData(
        upload_file, f'api/v1/courses/{course}/files',
        base=base, access_token=access_token
    )
    req.add_data('local_file', local_file)
    req.add_data('name', remote_name)
    req.add_data('size', getsize(local_file))
    req.add_data('parent_folder_path', upload_path)
    req.add_data('on_duplicate', 'overwrite' if overwrite else 'rename')
    req.add_optional_data('content_type', content_type)

    return req.submit()


def import_qti_quiz(course, qti_file, access_token=None, base=None):
    """
    Upload a file to the course 'files'. This is specifically meant to upload
    quizzes created by R/exams, namely `exams2canvas` function, so it is not as
    flexible as it could be.

    Parameters:
        course: the course id
        qti_file: the local path to the file.  The file must exist, and not be
            huge, and it must be a qti zipped file
        access_token: access token
        base: base url of canvas server

    Returns:
        Json of the migration info
    """

    req = RequestWithData(
        upload_file, f'api/v1/courses/{course}/content_migrations',
        base=base, access_token=access_token
    )
    req.add_data('local_file', qti_file)
    req.add_data('migration_type', 'qti_converter')
    req.add_data('pre_attachment[name]', basename(qti_file))
    req.add_data('pre_attachment[size]', getsize(qti_file))

    res = req.submit()

    migration_id = res['init']['id']

    req = Request(
        get_to_json,
        f"/api/v1/courses/{course}/content_migrations/{migration_id}",
        base=base, access_token=access_token
    )

    return req.submit()


def get_list_of_courses(access_token=None, base=None):
    """
    Returns a list of current user's courses, as a list of json course data,
    one record for each course.
    Parameters:
        access_token: access token
        base: base url of canvas server
    """

    req = Request(get_all_pages, 'api/v1/courses', {}, base, access_token)

    return req.submit()


def get_students(course, base=None, access_token=None):
    """Lists all students in a given course.
    Parameters:
        course: course ID
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one
    Returns a list of dicts, one for each student
    """

    req = Request(
        get_all_pages, f'api/v1/courses/{course}/users', base, access_token
    )
    req.add_param('enrollment_type', 'student')

    return req.submit()


def find_user_by_login_id(login_id, base=None, access_token=None):
    """Search for a user with a given sis_login_id, if found, return user
    profile.
    Parameters:
        login_id: user's sis_login_id
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one
    Returns a request result
    """

    req = Request(
        get_to_json, f"/api/v1/users/sis_login_id:{login_id}/profile",
        base, access_token
    )

    return req.submit()


def enroll_user_by_login_id(course, login_id, base=None, access_token=None):
    """Enrolls a user with a given sis_login_id, if found. Returns user
    profile.
    Parameters:
        course: course ID
        login_id: user's sis_login_id
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one
    Returns a request result
    """

    json1 = find_user_by_login_id(login_id, base, access_token)

    if 'Error' in json1:
        return {**json1, "msg": "HTTP error"}

    if "login_id" in json1 and json1["login_id"] == login_id and "id" in json1:
        id = json1['id']
    else:
        return {"Error": 1, "msg": "Could not find user", "json": json1}

    req = RequestWithData(
        post_to_json, f'api/v1/courses/{course}/enrollments',
        base, access_token
    )
    req.add_data('enrollment[user_id]', id)
    req.add_data('enrollment[enrollment_state]', 'active')

    return req.submit()


def get_enrollments(course, base=None, access_token=None):
    """Lists all enrollments in a given course.
    Parameters:
        course: course ID
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one
    Returns a list of dicts, one for each enrollment
    """

    req = Request(
        get_all_pages, f'api/v1/courses/{course}/enrollments',
        base, access_token
    )

    return req.submit()


def enrollment_stop(
        course, user_id, task="conclude", base=None, access_token=None):
    """Modifies an enrollment of given user in given course.
    Parameters:
        course: course ID
        user_id: user id (numerical Canvas id)
        task: how should the enrollment change?
                "conclude", "delete", "deactivate"
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one
    Returns a request result
    """

    req = Request(
        delete_to_json, f'api/v1/courses/{course}/enrollments/{user_id}',
        base, access_token
    )
    req.add_param("task", task)

    return req.submit()


def create_appointment_group(course_list, title, description, location,
                             time_slots, publish=False, max_part=None,
                             min_per_part=None, max_per_part=1, private=True,
                             base=None, access_token=None):
    """
    Create an appointment group.
    Parameters:
        course_list: a list of course ids.  Students in those courses
            will be allowed to sign up
        title: a title of the group
        description: a description
        location: a string, location of the appointment
        time_slots: a list of pairs of times - (start, end) for each
            slot
        publish: publish right away or wait (can't be unpublished)
        max_part: maximum number of participants per appointment (default
            no limit)
        min_per_part: minimum number of appointment a participant must sign
            up for (default no minimum)
        max_per_part: maximum number of appointment a participant must sign
            up for (default unknown, we set it to 1)
        private: participants cannot see each others names
    """

    req = RequestWithData(
        post_to_json, "/api/v1/appointment_groups",
        base, access_token
    )
    req.add_data('appointment_group[context_codes][]',
                 [f'course_{id}' for id in course_list])
    req.add_data('appointment_group[title]', title)
    req.add_data('appointment_group[description]', description)
    req.add_data('appointment_group[location_name]', location)
    req.add_data('appointment_group[participants_per_appointment]', max_part)
    req.add_data('appointment_group[max_appointments_per_participant]',
                 max_per_part)
    req.add_data('appointment_group[min_appointments_per_participant]',
                 min_per_part)
    req.add_data('appointment_group[participant_visibility]',
                 'private' if private else 'protected')
    req.add_data('appointment_group[publish]', publish)
    for i, slot in enumerate(time_slots):
        req.add_data(f'appointment_group[new_appointments][{i+1}][]', slot)

    return req.submit()


def get_group_categories(course, base=None, access_token=None):
    """Lists all group categories in a given course.
    Parameters:
        course: course ID
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one
    Returns a list of dicts, one for each category
    """

    req = Request(
        get_all_pages, f'api/v1/courses/{course}/group_categories',
        base, access_token
    )

    return req.submit()


def get_groups(course, category=None, base=None, access_token=None):
    """
    Lists groups in a course.  If category ID is given, only list the groups
    in this category.  Note that in that case, course id is ignored.

    Parameters:
        course: course ID
        category: optional string or int, an ID of a group category.
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one
    Returns a list of dicts, one for each group.
    """

    if category is None:
        api = f'api/v1/courses/{course}/groups'
    else:
        api = f'api/v1/group_categories/{category}/groups'

    req = Request(
        get_all_pages, api,
        base, access_token
    )

    return req.submit()


def get_group_members(group, base=None, access_token=None):
    """
    Get a list of all members of a group"

    Parameters:
        group: group ID
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one

    Returns:
        a list of users
    """

    req = Request(
        get_all_pages, f"/api/v1/groups/{group}/users",
        base, access_token
    )

    return req.submit()


def get_assignments(course, search=None, bucket=None, base=None,
                    access_token=None):
    """
    Get a list of assignments for a course.

    Parameters:
        course: course ID
        search: an optional search term for assignment names
        bucket: optional, if included, only return certain assignments
            depending on due date and submission status. Valid buckets are
            “past”, “overdue”, “undated”, “ungraded”, “upcoming”,
            and “future”.,
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one

    Returns:
        list of assignments
    """

    req = Request(
        get_all_pages, f"/api/v1/courses/{course}/assignments",
        base, access_token
    )
    req.add_optional_param('search_term', search)
    req.add_optional_param('bucket', bucket)

    return req.submit()


# TODO: This will need to be simplified

def get_submissions(course, assignment=None, student=None, assignments=None,
                    students=None, grouped=True, base=None, access_token=None):
    """
    Get assignment(s) submission(s) from the course.

    Parameters:
        course: course ID
        assignment: an assignment ID, if a single assignment is to be obtained
        student: a student id, if a single students' assignments should be
            obtained
        assignments: a list of assignment ids.  If both assignment and
            assignments are None, obtain all assignments
        students: a list of student ids. If both student and students are None,
            obtain assignments for all students
        grouped: If multiple assignments for multiple students are to be
            listed, should they be grouped by students?  Otherwise ignored.
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one

    Returns a list of submissions.
    """

    if student is not None and isinstance(students, list):
        if student not in students:
            students += [student]
        student = None

    # Now at least one of student and students is None

    if assignment is not None and isinstance(assignments, list):
        if assignment not in assignments:
            assignments += [assignment]
        assignment = None

    # Now at least one of assignment and assignments is None

    # There are three API points:
    #  - single assignment for single student
    #  - single assignment, all students
    #  - selected (or all) assignments for selected (or all) students

    api = None
    if assignment is not None:  # Single assignment
        if student is not None:    # and single student
            api = f"/api/v1/courses/{course}"
            f"/assignments/{assignment}"
            f"/submissions/{student}"
        elif students is None:     # and all students
            api = f"/api/v1/courses/{course}"
            f"/assignments/{assignment}/submissions"
        else:                      # and multiple students
            assignments = [assignment]
            assignment = None

        if api is not None:
            req = Request(
                get_all_pages, api,
                base, access_token
            )
            return req.submit()

    if student is not None:
        students = [student]
        student = None

    student_list = "all" if students is None else ','.join(
        str(id) for id in students
    )
    assignment_list = None if assignments is None else ','.join(
        str(id) for id in assignments
    )

    req = Request(
        get_all_pages, f"/api/v1/courses/{course}/students/submissions",
        base, access_token
    )
    req.add_param('grouped', 1 if grouped else 0)
    req.add_param('student_ids[]', student_list)
    req.add_optional_param('assignment_ids[]', assignment_list)

    return req.submit()


def create_grade_data(grades, assignment_id=None):
    """
    A help function that takes an assignment id and a dict of student
    grades in the form {student_id: grade} and converts it into a dict
    suitable for submission to Canvas server.
    """

    grade_dict = {id: {"posted_grade": grade} for id, grade in grades.items()}

    if assignment_id is None:
        return {"grade_data": grade_dict}
    else:
        return {"grade_data": {assignment_id: grade_dict}}


def update_grades(course, assignment_id, grades, base=None, access_token=None):
    """
    Submit grades for an assignment. WARNING: This does not seem to work,
    I keep getting an internal server error from it.

    Parameters:
        course: the course ID
        assignment_id: the ID of the assignment
        grades: a dict with student grades in the form {student_id: grade}
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one

    Returns something, hopefully
    """

    data = create_grade_data(grades)

    req = RequestWithData(
        requests.post,
        f"/api/v1/courses/{course}"
        f"/assignments/{assignment_id}"
        "/submissions/update_grades",
        base, access_token
    )
    req.add_data_dict(data)

    return req.submit()


def update_grade(course, assignment_id, student_id, grade, base=None,
                 access_token=None):
    """
    Submit a single grade for an assignment.

    Parameters:
        course: the course ID
        assignment_id: the ID of the assignment
        student_id: an id of the graded student
        grade: a string with an integer of floating point number, optionally
            followed by a percent, or letter grade
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one

    Returns something, hopefully
    """

    req = RequestWithData(
        requests.put,
        f"/api/v1/courses/{course}"
        f"/assignments/{assignment_id}"
        f"/submissions/{student_id}",
        base, access_token
    )
    req.add_data("submission[posted_grade]", grade)

    return req.submit()


def comment_on_submission(course, assignment_id, student_id, comment,
                          base=None, access_token=None):
    """
    Submit a comment on a submission.

    Parameters:
        course: the course ID
        assignment_id: the ID of the assignment
        student_id: an id of the graded student
        comment: a string with a comment for the submission
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one

    Returns something, hopefully
    """

    req = RequestWithData(
        requests.put,
        f"/api/v1/courses/{course}"
        f"/assignments/{assignment_id}"
        f"/submissions/{student_id}",
        base, access_token
    )
    req.add_data("comment[text_comment]", comment)

    return req.submit()


def course(course):
    """
    Utility function that takes a course id and prefixes it with 'course_'.
    """

    return f"course_{course}"


def group(group):
    """
    Utility function that takes a group id and prefixes it with 'group_'.
    """

    return f"group_{group}"


def create_conversation(recipients, subject, body, force_new=False,
                        is_group_conversation=False,
                        context=None, base=None, access_token=None):
    """
    Create a conversation.

    Parameters:
        recipients: list of recipient ids.  Can include groups or courses by
                    prefixing them with 'group_' or 'course_'
        subject: the subject of the conversation
        body: the body of the conversation
        force_new: force new conversation even if there is an existing
                    conversation with the same recipients
        is_group_conversation: if true, create a group conversation instead of
                                bunch of individual conversations with each
                                recipient
        context: group of course that is the context of the conversation.
                    Course or group ID prefixed with 'course_' or 'group_'
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one

    Returns something, hopefully
    """

    req = RequestWithData(
        requests.post, "/api/v1/conversations",
        base, access_token
    )
    req.add_data('recipients[]', recipients)
    req.add_data('subject', subject)
    req.add_data('body', body)
    req.add_data('scope', 'unread')
    req.add_data('force_new', 1 if force_new else 0)
    req.add_data('group_conversation', 1 if is_group_conversation else 0)
    req.add_optional_data('context_code', context)

    return req.submit()


def get_quiz_submissions(course, quiz_id, base=None, access_token=None):
    """
    Get assignment(s) submission(s) from the course.

    Parameters:
        course: the course ID
        quiz_id: the ID of the quiz
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one

    Returns a list of submissions for the quiz
    """

    req = Request(
        get_to_json, f"/api/v1/courses/{course}/quizzes/{quiz_id}/submissions",
        base, access_token
    )

    return req.submit()


def get_quiz_submission_answers(submission_id, base=None, access_token=None):
    """
    Get assignment(s) submission(s) from the course.

    Parameters:
        submission_id: the ID of the individual submission from which to
                       download
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one

    Returns a list of answers for the particular submission.
    """

    req = Request(
        get_to_json, f"/api/v1/quiz_submissions/{submission_id}/questions",
        base, access_token
    )

    return req.submit()


def get_favorite_courses(base=None, access_token=None):
    """
    Get current users list of favorite courses.

    Parameters:
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one
    """

    req = Request(
        get_all_pages, "/api/v1/users/self/favorites/courses",
        base, access_token
    )

    return req.submit()


def add_course_to_favorites(course, base=None, access_token=None):
    """
    Add a course to the current users list of favorite courses.  If the course
    already is a favorite, nothing happens.

    Parameters:
        course: a course id, string or integer
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one

    Returns a favorite.
    """

    req = RequestWithData(
        post_to_json, f"/api/v1/users/self/favorites/courses/{course}",
        base, access_token
    )

    return req.submit()


def remove_course_from_favorites(course, base=None, access_token=None):
    """
    Removes a course from the current users list of favorite courses.

    Parameters:
        course: a course id, string or integer
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one

    Returns a favorite.
    """

    req = Request(
        delete_to_json, f"/api/v1/users/self/favorites/courses/{course}",
        base, access_token
    )

    return req.submit()


def get_course_tabs(course, base=None, access_token=None):
    """
    Lists the navigation tabs for the course.  Include external tools.

    Parameters:
        course: the course id
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one
    """

    req = Request(
        get_all_pages, f"/api/v1/courses/{course}/tabs",
        base, access_token
    )
    req.add_param('include[]', 'external')

    return req.submit()


def update_course_tab(course, tab, position, hidden=False,
                      base=None, access_token=None):
    """
    Update (move, hide) a course navigation tab.

    Parameters:
        course: the course id
        tab: the tab id
        position: 1 based position of the tab
        hidden: should the tab be hidden
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one
    """

    req = RequestWithData(
        put_to_json, f"/api/v1/courses/{course}/tabs/{tab}",
        base, access_token
    )
    req.add_data('hidden', hidden)
    req.add_data('position', position)

    return req.submit()


def create_grading_standard(course, name, grades, cutoffs,
                            base=None, access_token=None):
    """
    Creates a new grading standard for a course.

    Parameters:
        course: the course id
        name: title of the standard
        grades: list of strings, names of the grades, in descending order
        cutoffs: list of numbers, cut offs for the grades.  Should have one
            less item than `grades`.
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one
    """

    if len(cutoffs) == len(grades) - 1:
        cutoffs += [0]

    req = RequestOrderedData(
        post_to_json, f"/api/v1/courses/{course}/grading_standards",
        base, access_token
    )
    req.add_data('title', name)
    for g, c in zip(grades, cutoffs):
        req.add_data('grading_scheme_entry[][name]', g)
        req.add_data('grading_scheme_entry[][value]', c)

    return req.submit()

# Modules:


def list_modules(course, items=False, details=False, search=None, student=None,
                 base=None, access_token=None):
    """
    Lists modules in a course.

    Parameters:
        course: the course id
        items: a boolean, whether to include lists of items for each modules.
            Canvas may decide to ignore this if there are too many items.
        details: a boolean, whether to include additional details about items.
            Only applies if `items` is true.
        search: search string to limit modules to those that match.
        student: include completion info for this student id.
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one

    Returns:
        List of modules
    """

    req = Request(
        get_all_pages, f"/api/v1/courses/{course}/modules",
        base, access_token
    )
    if items:
        req.add_param('include',
                      ["items"] + ([] if not details else ["content_details"]))
    req.add_optional_param('search_term', search)
    req.add_optional_param('student_id', student)

    return req.submit()


def show_module(course, module, items=False, details=False, student=None,
                base=None, access_token=None):
    """
    Give information about a single module

    Parameters:
        course: the course id
        module: module id
        items: a boolean, whether to include lists of items for each modules.
            Canvas may decide to ignore this if there are too many items.
        details: a boolean, whether to include additional details about items.
            Required items to be true.
        student: include completion info for this student id.
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one

    Returns:
        Response with module info, when successful
    """

    req = Request(
        get_to_json, f"/api/v1/courses/{course}/modules/{module}",
        base, access_token
    )
    if items:
        req.add_param('include',
                      ["items"] + ([] if not details else ["content_details"]))
    req.add_optional_param('student_id', student)

    return req.submit()


def create_module(course, name, position, unlock_at=None, sequential=False,
                  prereqs=None, publish_final_grade=False,
                  base=None, access_token=None):
    """
    Creates a new module for the course.

    Parameters:
        course: the course id
        name: the name of the module
        position: an integer position of the module in the course, 1 based
        unlock_at: date to unlock the module, hopefully optional
        sequential: Do the items have to be unlocked in order
        prereqs: list of ids of modules that must be done before this one is
            unlocked
        publish_final_grade: no idea, make it False
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one

    Returns:
        a response with the module, if successful
    """

    req = RequestWithData(
        post_to_json, f"/api/v1/courses/{course}/modules",
        base, access_token
    )
    req.add_data("module[name]", name)
    req.add_data("module[position]", position)
    req.add_data("module[require_sequential_progress]", sequential)
    req.add_data("module[publish_final_grade]", publish_final_grade)
    req.add_optional_data("module[unlock_at]", unlock_at)
    req.add_optional_data("module[prerequisite_module_ids]", prereqs)

    return req.submit()


def delete_module(course, module, base=None, access_token=None):
    """
    Delete a module.

    Parameters:
        course: the course id
        module: module id
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one

    Returns:
        Response with module info, when successful
    """

    req = Request(
        delete_to_json, f"/api/v1/courses/{course}/modules/{module}",
        base, access_token
    )

    return req.submit()


def list_module_items(course, module, details=False, search=None, student=None,
                      base=None, access_token=None):
    """
    Lists items in a module.

    Parameters:
        course: the course id
        module: the module id
        details: a boolean, whether to include additional details about items.
        search: search string to limit modules to those that match.
        student: include completion info for this student id.
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one

    Returns:
        List of items
    """

    req = Request(
        get_all_pages, f"/api/v1/courses/{course}/modules/{module}/items",
        base, access_token
    )
    if details:
        req.add_param('include', ["content_details"])
    req.add_optional_param('search_term', search)
    req.add_optional_param('student_id', student)

    return req.submit()


def show_module_item(course, module, item, details=False, student=None,
                     base=None, access_token=None):
    """
    Give information about a single item

    Parameters:
        course: the course id
        module: module id
        item: item id
        details: a boolean, whether to include additional details about the
            item.
        student: include completion info for this student id.
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one

    Returns:
        Json with item info, when successful
    """

    req = Request(
        requests.get,
        f"/api/v1/courses/{course}/modules/{module}/items/{item}",
        base, access_token
    )
    req.add_optional_param('include', ["content_details"])
    req.add_optional_param('student_id', student)

    return req.submit()


def create_module_item(course, module, title, position, itemtype, indent=0,
                       content=None, page_url=None, external_url=None,
                       new_tab=True, base=None, access_token=None):
    """
    Creates a new item in the module.

    Parameters:
        course: the course id
        module: module id
        title: title of the item
        position: an integer position of the item in the module, 1 based
        itemtype: type of item.  One of "File", "Page", "Discussion",
            "Assignment", "Quiz", "SubHeader", "ExternalUrl", "ExternalTool"
        indent: indent amount for the item
        content: content id for "File", "Discussion", "Assignment", "Quiz" or
            "ExternalTool"
        page_url: page suffix for "Page" (whatever that means)
        external_url: url for "ExternalUrl"
        new_tab: should "ExternalTool" open in a new tab
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one

    Note that completion requirements are not implemented at the moment.

    Returns:
        a response with the item, if successful
    """

    # Some combinations are required while other are ignored.  Do not sort the
    # mess right now and trust that caller knows what they are doing.

    req = RequestWithData(
        requests.post, f"/api/v1/courses/{course}/modules/{module}/items",
        base, access_token
    )
    req.add_data("module_item[title]", title)
    req.add_data("module_item[type]", itemtype)
    req.add_data("module_item[position]", position)
    req.add_data("module_item[indent]", indent)
    req.add_data("module_item[new_tab]", (1 if new_tab else 0))
    req.add_optional_data("module_item[content_id]", content)
    req.add_optional_data("module_item[page_url]", page_url)
    req.add_optional_data("module_item[external_url]", external_url)

    return req.submit()


def delete_module_item(course, module, item, base=None, access_token=None):
    """
    Delete a module item.

    Parameters:
        course: the course id
        module: module id
        item: item id
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one

    Returns:
        Response with item info, when successful
    """

    req = Request(
        requests.delete,
        f"/api/v1/courses/{course}/modules/{module}/items/{item}",
        base, access_token
    )

    return req.submit()


# External tools API.  The whole external tools stuff is complicated and messy,
# this here just creates a simple external tool in a course, with minimal
# options.

def create_external_tool(course, name, privacy_level, key, secret,
                         url=None, domain=None, base=None, access_token=None):
    """
    Creates a new external tool for a course.

    Parameters:
        course: the course id
        name: title of the tool
        privacy_level: "anonymous", "name_only", "public"
        key: a "consumer key" for the tool
        secret: a "shared secret" for the tool
        url: the url to match links against
        domain: the domain to match links against
            (exactly one of url and domain must be set.  If both are set, url
             is used. If none is set, ValueError is raised.)
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one
    """

    if url is None and domain is None:
        raise ValueError("One of url and domain must be given.")

    req = RequestWithData(
        post_to_json, f"/api/v1/courses/{course}/external_tools",
        base, access_token
    )
    req.add_data("name", name)
    req.add_data("privacy_level", privacy_level)
    req.add_data("consumer_key", key)
    req.add_data("shared_secret", secret)
    if url is None:
        req.add_data("domain", domain)
    else:
        req.add_data("url", url)

    return req.submit()

# Rubrics.  Rubrics in Canvas are a mess, and I do not understand them, but
# what's below seems to work.  It uses a dict describing a rubric that looks
# like this:
# rubric = {
# 'title': 'A string',
# 'description': 'Anozer string',
# 'criteria': [
# {
# 'description': "A string",
# 'long_description': "A longer string",
# 'points': 10,
# 'use_range': True,
# 'ratings': [
# {
# 'description': "Blah blah",
# 'points': 0
# },
# {
# 'description': "Bloh bloh",
# 'points': 10
# }
# ]
# },
# {
# 'description': "A string 2",
# 'long_description': "A longer string 2",
# 'points': 5,
# 'use_range': True,
# 'ratings': [
# {
# 'description': "Blah blah",
# 'points': 0
# },
# {
# 'description': "Blih blih",
# 'points': 3
# },
# {
# 'description': "Bloh bloh",
# 'points': 5
# }
# ]
# }
# ]
# }


def criterion_to_data(criterion, number, data=None):
    """
    Translate a dict describing a rubric criterion to data to send to server.

    Parameters:
        criterion: a dict with a single criterion data
        number: a criterion number
        data: an existing dict to which the data will be added

    Returns:
        a dict with rubric data to send to server
    """

    if data is None:
        data = {}

    data["rubric[criteria][{}][description]".format(
        number)] = criterion['description']
    if 'long_description' in criterion:
        data['rubric[criteria][{}][long_description]'.format(
            number)] = criterion['long_description']
    data['rubric[criteria][{}][points]'.format(
        number)] = criterion['points']  # Ignored?
    if 'use_range' in criterion:
        data['rubric[criteria][{}][criterion_use_range]'.format(
            number)] = criterion['use_range']
    if criterion['ratings']:
        for j, rating in enumerate(criterion['ratings']):
            data['rubric[criteria][{}][ratings][{}][description]'.format(
                number, j)] = rating['description']
            data['rubric[criteria][{}][ratings][{}][points]'.format(
                number, j)] = rating['points']
    else:  # default ratings,  Canvas creates those but messes up the points!
        data['rubric[criteria][{}][ratings][0][description]'.format(
            number)] = "Full Points"
        data['rubric[criteria][{}][ratings][0][points]'.format(
            number)] = criterion['points']
        data['rubric[criteria][{}][ratings][1][description]'.format(
            number)] = "No Points"
        data[f'rubric[criteria][{number}][ratings][1][points]'] = 0

    return data


def rubric_to_data(assignment, rubric, comments=True):
    """
    Translate a dict with rubric description to data to send to server.

    Parameters:
        assignment: an assignment ID to associate the rubric with
        rubric: a dict with rubric data.
        comments: whether to use free form comments when grading

    Returns:
        a dict with rubric data to send to server
    """

    data = {
        'rubric_association[association_id]': assignment,
        'rubric_association[association_type]': 'Assignment',
        'rubric_association[use_for_grading]': True,
        'rubric_association[purpose]': 'grading',
        'rubric[free_form_criterion_comments]': comments,
        'rubric[title]': rubric['title'],
        'rubric[description]': rubric['description']
    }

    if 'criteria' in rubric:
        for i, criterion in enumerate(rubric['criteria']):
            data = criterion_to_data(criterion, i, data)

    return data


def create_rubric_for_assignment(course, assignment, rubric,
                                 comments=True,
                                 base=None, access_token=None):
    """
    Creates a new rubric and associate it to an assignment

    Parameters:
        course: the course id
        assignment: the assignment id
        rubric: a dict describing the rubric
        comments: whether to allow free style comments while grading.
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one

    Returns:
        whatever it is that Canvas sends back
    """

    req = RequestWithData(
        post_to_json, f"/api/v1/courses/{course}/rubrics",
        base, access_token
    )
    req.add_data_dict(rubric_to_data(assignment, rubric, comments))

    return req.submit()


def add_criterion_to_rubric(course, rubricid, criterion, number,
                            base=None, access_token=None):
    """
    Adds a new criterion to a rubric

    Parameters:
        course: the course id
        rubricid: an id of the rubric
        criterion: a dict describing the criterion
        number: the number of the criterion
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one

    Returns:
        whatever it is that Canvas sends back
    """

    req = RequestWithData(
        put_to_json, f"/api/v1/courses/{course}/rubrics/{rubricid}",
        base, access_token
    )
    req.add_data_dict(criterion_to_data(criterion, number))

    return req.submit()
