"""
A module for interacting with Instructure Canvas

Global parameters (most can also be changed on individual function calls):
    base_url: string, containing the base url of canvas server
    token: string, containing the user access token.
    this_year: current year, for making class schedules
"""
import requests
import arrow
import markdown
from os.path import expanduser

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

def get_all_pages(orig_url, params={}):
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
    while True:
        resp = requests.get(url, params=params)
        json += resp.json()
        if 'next' not in resp.links:
            return json
        url = resp.links['next']['url']
        params = {'access_token': params['access_token']}

def contact_server(contact_function, location, data, base=None,
                   access_token=None):
    """
    Abstracting a server request. Builds a url from base and location, adds
    access_token if given, or default token, to data dict, and calls
    contact_function with the url and data.  Returns the result of the
    contact_function.
    """
    params = data.copy() #prevent them from being clobbered
    params['access_token'] = token if access_token is None else access_token

    return contact_function((base_url if base is None else base) + location,
                            params)

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
                           markdown.markdown(markdown_body, ['extra'])},
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
                                  markdown.markdown(markdown_body, ['extra']),
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
                                                    ['extra']),
                              'wiki_page[published]':'1' if published else '0'
                          },
                          base, access_token)

def create_assignment(course, name, markdown_description, points, due_at,
                      group_id, submission_types="on_paper",
                      access_token=None, base=None):
    """
    Creates a simple assignment in the given course.
    Parameters:
        course: a course ID, int or string
        name: the name of the assignment
        markdown_description: description of the assignment, in markdown
        points: max number of points for the assignment
        due_at: due date for the assignment, in YYYY-MM-DD
        group_id: assignment group to place the assignment into
        submission_types: how should it be submitted
        access_token: access token
        base: base url of canvas server
    """


    return contact_server(requests.post,
                          'api/v1/courses/{}/assignments'.format(course),
                          {
                              'assignment[name]':name,
                              'assignment[description]':
                                  markdown.markdown(markdown_description,
                                                    ['extra']),
                              'assignment[submission_types]':submission_types,
                              'assignment[points_possible]': points,
                              'assignment[due_at]':due_at,
                              'assignment[group_id]': group_id,
                              'assignment[published]':1
                          },
                          base, access_token)

def create_redirect_tool(course, text, url, default=True, access_token=None,
                         base=None):
    """
    Create a redirect tool for course navigation.
    Parameters:
        course: the course id
        text: the text that will be displayed in the navigation
        url: the redirection url
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
                              'text':text,
                              'not_selectable':True,
                              'course_navigation[url]':url,
                              'course_navigation[enabled]':True,
                              'course_navigation[text]':text,
                              'course_navigation[default]':default,
                              'description':"Redirects to " + url
                          },
                          base, access_token)

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
