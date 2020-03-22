"""
A module for interacting with Instructure Canvas

Global parameters (most can also be changed on individual function calls):
    base_url: string, containing the base url of canvas server
    token: string, containing the user access token.
    this_year: current year, for making class schedules
"""
from os.path import expanduser, getsize, basename
import requests
import arrow
import markdown

base_url = "https://svsu.instructure.com/"
token = 'An invalid token.  Redefine with your own'
this_year = int(arrow.now().format('YYYY'))


def read_access_token(file='~/.canvas/access_token'):
    "Read access token if available"
    global token
    try:
        with open(expanduser(file), 'r') as f:
            token = f.read().rstrip('\n')
    except:
        print("Could not read access token")

# The main purpose for this is that we cannot splat things into a dict :(
def calendar_event_data(course, title, description, start_at, end_at):
    """
    Creates a dict with parameters for calendar event data to be passed to
    `create_calendar_event`. Parameters:
        course: course id, string or int
        title: string, event title
        description: string, detailed event description
        start_at: starting time, in YYYY-MM-DDTHH:MMZZ format
        end_at: ending time, in YYYY-MM-DDTHH:MMZZ format
    """
    event_data = {
        'calendar_event[context_code]':'course_{}'.format(course),
        'calendar_event[title]':title,
        'calendar_event[description]':description,
        'calendar_event[start_at]':start_at,
        'calendar_event[end_at]':end_at,
    }
    return event_data

def get_all_pages(orig_url, params=None):
    """
    Auxiliary function that uses the 'next' links returned from the server to
    request additional pages and combine them together into one json response.
    Parameters:
        orig_url: the url for the original request
        params: a dict with the parameters for the original request (must
                    contain access token)
    Returns:
        A combined list of json results returned in all pages.
    Warning:
        Does not handle failure in any way! Make sure you don't kill your pets
        by accident.
    """
    url = orig_url
    json = []
    if params is None:
        params = {}
    while True:
        resp = requests.get(url, params=params)
        json += resp.json()
        if 'next' not in resp.links:
            return json
        url = resp.links['next']['url']
        params = {'access_token': params['access_token']}

def contact_server(contact_function, location, data=None, base=None,
                   access_token=None):
    """
    Abstracting a server request. Builds a url from base and location, adds
    access_token if given, or default token, to data dict, and calls
    contact_function with the url and data.  Returns the result of the
    contact_function.

    Also accepts a list of pairs as data.
    """
    if data is None:
        params = dict()
    else:
        params = data.copy() #prevent them from being clobbered
    if isinstance(params, dict):
        params['access_token'] = token if access_token is None else access_token
    else:
        params += [('access_token', token if access_token is None else access_token)]

    return contact_function((base_url if base is None else base) + location,
                            params=params)

def create_calendar_event(event_data, base=None, access_token=None):
    "Post an event described by `event_data` dict to a calendar"

    return contact_server(requests.post, 'api/v1/calendar_events.json',
                          event_data, base, access_token)

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

    return contact_server(get_all_pages, 'api/v1/calendar_events.json',
                          {
                              'type': 'event',
                              'start_date': start_date,
                              'end_date': end_date,
                              'context_codes[]': 'course_{}'.format(course),
                          },
                          base, access_token)

def list_calendar_events_all(course, base=None, access_token=None):
    """Lists all events in a given course.
    Parameters:
        course: course ID
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one
    """

    return contact_server(get_all_pages, 'api/v1/calendar_events.json',
                          {
                              'type': 'event',
                              'all_events': True,
                              'context_codes[]': 'course_{}'.format(course),
                          },
                          base, access_token)


def delete_event(event_id, base=None, access_token=None):
    """Deletes an event, specified by 'event_id'. Returns the event."""

    return contact_server(requests.delete,
                          'api/v1/calendar_events/{}'.format(event_id),
                          {
                              'cancel_reason': 'no reason',
                              'access_token':access_token
                          },
                          base, access_token)


def class_span(start, length):
    """Returns class starting and ending time in isoformat.  To be used with
    `calendar_event_data`. Parameters:
        start: an arrow object describing class starting time
        length: length of class in minutes
    """
    return start.isoformat(), start.replace(minutes=length).isoformat()

def firstclass(month, day, hour, minute, year=this_year):
    "A convenience function creating an arrow object for the first class in the semester"
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
                calendar_event_data(course, event[0], event[1],
                                    *class_span(classtime, length)),
                base, access_token)
        classtime = classtime.replace(days=2 if i%2 == 0 else 5)

def upload_syllabus_from_markdown(course, markdown_body, access_token=None,
                                  base=None):
    """
    Uploads syllabus body to a given course.
    Parameters:
        course: a course ID, int or string
        markdown_body: the body of syllabus in markdown
        access_token: access token
        base: base url of canvas server
    """

    return contact_server(requests.put, 'api/v1/courses/{}'.format(course),
                          {'course[syllabus_body]':
                           markdown.markdown(markdown_body, extensions=['extra'])},
                          base, access_token)

def post_announcement_from_markdown(course, title, markdown_body, access_token=None,
                                    base=None):
    """
    Post an announcement to a given course
    Parameters:
        course: a course ID, int or string
        title: the title of the announcement
        markdown_body: the body of the announcement in markdown
        access_token: access token
        base: base url of canvas server
    """

    return contact_server(requests.post,
                          'api/v1/courses/{}/discussion_topics'.format(course),
                          {
                              'title':title,
                              'message':
                                  markdown.markdown(markdown_body, extensions=['extra']),
                              'is_announcement':'1'
                          },
                          base, access_token)

def post_group_announcement_from_markdown(group, title, markdown_body, access_token=None,
                                          base=None):
    """
    Post an announcement to a given group
    Parameters:
        group: a group ID, int or string
        title: the title of the announcement
        markdown_body: the body of the announcement in markdown
        access_token: access token
        base: base url of canvas server
    """

    return contact_server(requests.post,
                          'api/v1/groups/{}/discussion_topics'.format(group),
                          {
                              'title':title,
                              'message':
                                  markdown.markdown(markdown_body, extensions=['extra']),
                              'is_announcement':'1'
                          },
                          base, access_token)

def create_page_from_markdown(course, title, markdown_body, published=True,
                              access_token=None, base=None):
    """
    Creates a wiki page in a given course
    Parameters:
        course: a course ID, int or string
        title: the title of the page
        markdown_body: the body of page in markdown
        published: if the page should be published
        access_token: access token
        base: base url of canvas server
    """

    return contact_server(requests.post,
                          'api/v1/courses/{}/pages'.format(course),
                          {
                              'wiki_page[title]':title,
                              'wiki_page[body]':
                                  markdown.markdown(markdown_body,
                                                    extensions=['extra']),
                              'wiki_page[published]':'1' if published else '0'
                          },
                          base, access_token)


# The following function was provided by Mark A. Lilly (marqpdx):

def update_page_from_markdown(course, title, markdown_body, url, published=True,
                              access_token=None, base=None):
    """
    updates a wiki page in a given course
    Parameters:
        course: a course ID, int or string
        title: the title of the page
        markdown_body: the body of page in markdown
        url: the url of this page in the current course
        published: if the page should be published
        access_token: access token
        base: base url of canvas server
    """

    return contact_server(requests.put,
                          'api/v1/courses/{}/pages/{}'.format(course, url),
                          {
                              'wiki_page[title]':title,
                              'wiki_page[body]':
                                  markdown.markdown(markdown_body,
                                                    extensions=['extra']),
                              'wiki_page[published]':'1' if published else '0'
                          },
                          base, access_token)

def get_assignment_groups(course, access_token=None, base=None):
    """
    Gets a list of all assignment groups for a course.
    Parameters:
        course: a course ID, int or string
        access_token: access token
        base: base url of canvas server
    """

    return contact_server(get_all_pages,
                          'api/v1/courses/{}/assignment_groups'.format(course),
                          {'include[]':'assignments'},
                          base, access_token)

def create_assignment(course, name, markdown_description, points, due_at,
                      group_id, submission_types="on_paper",
                      allowed_extensions=None, peer_reviews=False,
                      auto_peer_reviews=False, ext_tool_url = None,
                      ext_tool_new_tab = False,
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
            "online_quiz", "none", "on_paper", "discussion_topic", "external_tool",
            "online_upload", "online_text_entry", "online_url", "media_recording"
        allowed_extensions: if submission_types contains "online_upload", list
            of allowed file extensions
        peer_reviews: should the assignment be peer reviwed
        auto_peer_reviews: assign reviewers automatically
        ext_tool_url: url of external tool, is submission_types contains
            "external_tool".
        ext_tool_new_tab: Boolean, should external tool open in a new tab.
        access_token: access token
        base: base url of canvas server
    """

    #The Canvas API documentation is wrong or at least misleading, submitting a
    #hash for external_tool_assignment_tag causes internal server error. The
    #fields have to he sent separately.

    return contact_server(requests.post,
                          'api/v1/courses/{}/assignments'.format(course),
                          dict([
                              ('assignment[name]', name),
                              ('assignment[description]',
                                  markdown.markdown(markdown_description,
                                                    extensions=['extra'])),
                              ('assignment[submission_types]', submission_types),
                              ('assignment[points_possible]',  points),
                              ('assignment[due_at]', due_at),
                              ('assignment[assignment_group_id]',  group_id),
                              ('assignment[published]', 1),
                              ('assignment[peer_reviews]', peer_reviews),
                              ('assignment[automatic_peer_rewiews]',
                                auto_peer_reviews)
                          ] +
                              ([] if allowed_extensions is None
                                else [('assignment[allowed_extensions]',
                                      allowed_extensions)]) +
                              ([] if ext_tool_url is None
                               else [('assignment[external_tool_tag_attributes][url]',
                                      ext_tool_url),
                                     ('assignment[external_tool_tag_attributes][new_tab]',
                                      ext_tool_new_tab)])
                          ),
                          base, access_token)


def course_settings_set(course, settings, access_token=None, base=None):
    """
    Set settings in a course.
    Parameters:
        course: the course id
        settings: a dict with course settings to change.  Keys should be the parts inside
            the square brackets of the parameter names for the "Update a Course"
            API request
    """

    return contact_server(requests.put,
                          'api/v1/courses/{}'.format(course),
                          {
                              "course[{}]".format(k):v for k, v in settings.items()
                          },
                          base, access_token)


def create_redirect_tool(course, text, url, new_tab=False, default=True, access_token=None,
                         base=None):
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

    return contact_server(requests.post,
                          'api/v1/courses/{}/external_tools'.format(course),
                          {
                              'name':'Redirect to ' + text,
                              'privacy_level':'Anonymous',
                              'consumer_key':'N/A',
                              'shared_secret':'hjkl',
                              'url':'https://www.edu-apps.org/redirect',
                              'text':text,
                              'custom_fields[url]':url,
                              'custom_fields[new_tab]':(1 if new_tab else 0),
                              'not_selectable':True,
                              'course_navigation[enabled]':True,
                              'course_navigation[text]':text,
                              'course_navigation[default]':default,
                              'description':"Redirects to " + url
                          },
                          base, access_token)


def upload_file_to_course(course, local_file, upload_path, remote_name=None,
                          content_type=None, overwrite=False,
                          access_token=None, base=None):
    """
    Upload a file to the course 'files'.
    Parameters:
        course: the course id
        local_file: the local path to the file.  The file must exist, and not be
            huge
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

    response = contact_server(requests.post,
                              'api/v1/courses/{}/files'.format(course),
                              data=dict(
                                  [
                                      ('name', remote_name if remote_name is not None
                                       else basename(local_file)),
                                      ('size', getsize(local_file)),
                                      ('parent_folder_path', upload_path),
                                      ('on_duplicate', 'overwrite' if overwrite
                                       else 'rename')
                                  ] + ([('content_type', content_type)]
                                       if content_type is not None else [])),
                              base=base, access_token=access_token)
    response.raise_for_status()

    upload_url = response.json()["upload_url"]
    upload_params = response.json()["upload_params"]

    with open(local_file, 'rb') as file:
        return requests.post(upload_url, data=upload_params, files={'file':file})


def get_list_of_courses(access_token=None, base=None):
    """
    Returns a list of current user's courses, as a list of json course data,
    one record for each course.
    Parameters:
        access_token: access token
        base: base url of canvas server
    """

    return contact_server(get_all_pages, 'api/v1/courses', {},
                          base, access_token)


def get_students(course, base=None, access_token=None):
    """Lists all students in a given course.
    Parameters:
        course: course ID
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one
    Returns a list of dicts, one for each student
    """

    return contact_server(get_all_pages,
                          'api/v1/courses/{}/users'.format(course),
                          {'enrollment_type':'student'},
                          base, access_token)


def find_user_by_login_id(login_id, base=None, access_token=None):
    """Search for a user with a given sis_login_id, if found, return user
    profile.
    Parameters:
        login_id: user's sis_login_id
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one
    Returns a request result
    """

    return contact_server(requests.get,
                          "/api/v1/users/sis_login_id:{}/profile".format(login_id),
                          base, access_token)


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

    resp = find_user_by_login_id(login_id, base, access_token)

    if resp.status_code != 200:
        return resp

    json = resp.json()

    if "login_id" in json and json["login_id"] == login_id and "id" in json:
        id = resp.json()['id']
    else:
        return resp

    return contact_server(requests.post,
                          'api/v1/courses/{}/enrollments'.format(course),
                          {'enrollment[user_id]':id,
                           'enrollment[enrollment_state]':'active'},
                          base, access_token)


def get_enrollments(course, base=None, access_token=None):
    """Lists all enrollments in a given course.
    Parameters:
        course: course ID
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one
    Returns a list of dicts, one for each enrollment
    """

    return contact_server(get_all_pages,
                          'api/v1/courses/{}/enrollments'.format(course),
                          {},
                          base, access_token)

def enrollment_stop(course, user_id, task="conclude", base=None, access_token=None):
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

    return contact_server(requests.delete,
                          'api/v1/courses/{}/enrollments/{}'.format(course, user_id),
                          {"task":task},
                          base, access_token)


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

    return contact_server(requests.post, "/api/v1/appointment_groups",
                          dict([
                              ('appointment_group[context_codes][]',
                               ['course_{}'.format(id) for id in course_list]),
                              ('appointment_group[title]', title),
                              ('appointment_group[description]', description),
                              ('appointment_group[location_name]', location),
                              ('appointment_group[participants_per_appointment]',
                               max_part),
                              ('appointment_group[max_appointments_per_participant]',
                               max_per_part),
                              ('appointment_group[min_appointments_per_participant]',
                               min_per_part),
                              ('appointment_group[participant_visibility]',
                               'private' if private else 'protected'),
                              ('appointment_group[publish]', publish)] +
                              [('appointment_group[new_appointments][{}][]'.format(i+1),
                                slot) for i, slot in enumerate(time_slots)]
                          ),
                          base, access_token)


def get_group_categories(course, base=None, access_token=None):
    """Lists all group categories in a given course.
    Parameters:
        course: course ID
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one
    Returns a list of dicts, one for each category
    """

    return contact_server(get_all_pages,
                          'api/v1/courses/{}/group_categories'.format(course),
                          base, access_token)


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
        api = 'api/v1/courses/{}/groups'.format(course)
    else:
        api = 'api/v1/group_categories/{}/groups'.format(category)

    return contact_server(get_all_pages,
                          api,
                          base, access_token)

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

    return contact_server(get_all_pages,
                          "/api/v1/groups/{}/users".format(group),
                          base, access_token)

def get_assignments(course, search=None, bucket=None, base=None,
                    access_token=None):
    """
    Get a list of assignments for a course.

    Parameters:
        course: course ID
        search: an optional search term for assignment names
        bucket: optional, if included, only return certain assignments
            depending on due date and submission status. Valid buckets are “past”,
            “overdue”, “undated”, “ungraded”, “upcoming”, and “future”.
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one

    Returns:
        list of assignments
    """

    return contact_server(get_all_pages,
                          "/api/v1/courses/{}/assignments".format(course),
                          None if (search is None and bucket is None) else
                          dict(([] if search is None else [('search_term', search)]) +
                               ([] if bucket is None else [('bucket', bucket)])),
                          base, access_token)

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

    data = None
    if student is None:
        if assignment is None:
            data = dict(
                [('student_ids[]',
                  "all" if students is None else ','.join(str(id) for id
                                                          in students))] +
                ([] if assignments is None else ['assignments_ids[]',
                                                 ','.join(str(id) for id in
                                                          assignments)]) +
                [('grouped', 1 if grouped else 0)])
            api = "/api/v1/courses/{}/students/submissions".format(course)
        else:
            api = "/api/v1/courses/{}/assignments/{}/submissions".format(course,
                                                                         assignment)
    else:
        api = "/api/v1/courses/{}/assignments/{}/submissions/{}".format(course,
                                                                        assignment,
                                                                        student)

    return contact_server(get_all_pages, api, data, base, access_token)


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

    return contact_server(requests.get,
                          "/api/v1/courses/{}/quizzes/{}/submissions".format(
                              course, quiz_id),
                          base, access_token)


def get_quiz_submission_answers(submission_id, base=None, access_token=None):
    """
    Get assignment(s) submission(s) from the course.

    Parameters:
        submission_id: the ID of the individual submission from which to download
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one

    Returns a list of answers for the particular submission.
    """

    return contact_server(requests.get,
                          "/api/v1/quiz_submissions/{}/questions".format(submission_id),
                          base, access_token)


def get_favorite_courses(base=None, access_token=None):
    """
    Get current users list of favorite courses.

    Parameters:
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one
    """

    return contact_server(get_all_pages,
                          "/api/v1/users/self/favorites/courses",
                          base, access_token)

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

    return contact_server(requests.post,
                          "/api/v1/users/self/favorites/courses/{}".format(course),
                          base, access_token)

def remove_course_from_favorites(course, base=None, access_token=None):
    """
    Removes a course from the current users list of favorite courses.

    Parameters:
        course: a course id, string or integer
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one

    Returns a favorite.
    """

    return contact_server(requests.delete,
                          "/api/v1/users/self/favorites/courses/{}".format(course),
                          base, access_token)


def get_course_tabs(course, base=None, access_token=None):
    """
    Lists the navigation tabs for the course.  Include external tools.

    Parameters:
        course: the course id
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one
    """

    return contact_server(get_all_pages,
                          "/api/v1/courses/{}/tabs".format(course),
                          {'include[]':'external'},
                          base, access_token)


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

    return contact_server(requests.put,
                          "/api/v1/courses/{}/tabs/{}".format(course, tab),
                          {'hidden':hidden, 'position':position},
                          base, access_token)

def create_grading_standard(course, name, grades, cutoffs,
                            base=None, access_token=None):
    """
    Creates a new grading standard for a course.

    Parameters:
        course: the course id
        name: title of the standard
        grades: list of strings, names of the grades, in descending order
        cutoffs: list of numbers, cut offs for the grades.  Should have one less
            item than `grades`.
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one
    """

    if len(cutoffs) == len(grades) - 1:
        cutoffs += [0]

    # Canvas uses repeated header names and requires them in a specific order,
    # name, value, name, value.  I couldn't find a way to do that with
    # dictionaries, so now `contact_server` accepts lists of pairs as well.

    params = [('title', name)]
    for d in zip(grades, cutoffs):
        params += [('grading_scheme_entry[][name]', d[0]),
                   ('grading_scheme_entry[][value]', d[1])]

    return contact_server(requests.post,
                          "/api/v1/courses/{}/grading_standards".format(course),
                          params,
                          base, access_token)

## Modules:

def list_modules(course, items=False, details=False, search=None, student=None,
                 base=None, access_token=None):
    """
    Lists modules in a course.

    Parameters:
        course: the course id
        items: a boolean, whether to include lists of items for each modules.
            Canvas may decide to ignore this if there are too many items.
        details: a boolean, whether to include additional details about items.
            Required items to be true.
        search: search string to limit modules to those that match.
        student: include completion info for this student id.
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one

    Returns:
        List of modules
    """

    if items:
        includes = [("include", ["items"] +
                     ([] if not details else ["content_details"]))]
    else:
        includes = []

    return contact_server(get_all_pages,
                          "/api/v1/courses/{}/modules".format(course),
                          None if (not items and not search and not student)
                          else dict(includes +
                                    ([] if search is None
                                        else [('search_term', search)]) +
                                    ([] if student is None
                                        else [('student_id', student)])),
                          base, access_token)


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

    if items:
        includes = [("include", ["items"] +
                     ([] if not details else ["content_details"]))]
    else:
        includes = []

    return contact_server(requests.get,
                          "/api/v1/courses/{}/modules/{}".format(course, module),
                          None if (not items and not student)
                          else dict(includes +
                                    ([] if student is None
                                        else [('student_id', student)])),
                          base, access_token)


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

    return contact_server(requests.post,
                          "/api/v1/courses/{}/modules".format(course),
                          dict([("module[name]", name),
                                ("module[position]", position),
                                ("module[require_sequential_progress]",
                                 sequential),
                                ("module[publish_final_grade]",
                                 publish_final_grade)] +
                                ([] if unlock_at is None
                                  else [("module[unlock_at]", unlock_at)]) +
                                ([] if prereqs is None
                                  else [("module[prerequisite_module_ids]",
                                         prereqs)])
                               ),
                          base, access_token)


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

    return contact_server(requests.delete,
                          "/api/v1/courses/{}/modules/{}".format(course, module),
                          None, base, access_token)


## Module items

def list_module_items(course, module, details=False, search=None, student=None,
                      base=None, access_token=None):
    """
    Lists modules in a course.

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

    return contact_server(get_all_pages,
                          "/api/v1/courses/{}/modules/{}/items".format(course, module),
                          None if (not details and not search and not student)
                          else dict(([] if details is None
                                        else [('include', ["content_details"])]) +
                                    ([] if search is None
                                        else [('search_term', search)]) +
                                    ([] if student is None
                                        else [('student_id', student)])),
                          base, access_token)


def show_module_item(course, module, item, details=False, student=None,
                     base=None, access_token=None):
    """
    Give information about a single item

    Parameters:
        course: the course id
        module: module id
        item: item id
        details: a boolean, whether to include additional details about the item.
        student: include completion info for this student id.
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one

    Returns:
        Response with item info, when successful
    """

    return contact_server(requests.get,
                          "/api/v1/courses/{}/modules/{}/items/{}".format(course,
                                                                          module,
                                                                          item),
                          None if (not details and not student)
                               else dict(([] if details is None
                                        else [('include', ["content_details"])]) +
                                    ([] if student is None
                                        else [('student_id', student)])),
                          base, access_token)


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

    return contact_server(requests.post,
                          "/api/v1/courses/{}/modules/{}/items".format(course,
                                                                       module),
                          dict([("module_item[title]", title),
                                ("module_item[type]", itemtype),
                                ("module_item[position]", position),
                                ("module_item[indent]", indent)] +
                                ([] if content is None
                                  else [("module_item[content_id]", content)]) +
                                ([] if page_url is None
                                  else [("module_item[page_url]", page_url)]) +
                                ([] if external_url is None
                                  else [("module_item[external_url]", external_url)]) +
                                ([] if new_tab is None
                                  else [("module_item[new_tab]", new_tab)])
                               ),
                          base, access_token)


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

    return contact_server(requests.delete,
                          "/api/v1/courses/{}/modules/{}/items/{}".format(course,
                                                                          module,
                                                                          item),
                          None, base, access_token)



## External tools API.  The whole external tools stuff is complicated and messy,
## this here just creates a simple external tool in a course, with minimal
## options.

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
             is used. If none is set, strange things may happen.)
        base: optional string, containing the base url of canvas server
        access_token: optional access token, if different from global one
    """

    return contact_server(requests.post,
                          "/api/v1/courses/{}/external_tools".format(course),
                          dict([("name", name),
                                ("privacy_level", privacy_level),
                                ("consumer_key", key),
                                ("shared_secret", secret),
                                ("domain", domain) if url is None else ("url", url)]),
                          base, access_token)
