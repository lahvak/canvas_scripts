"""
A module for posting stuff to Instructure Canvas

Global parameters (most can also be changed on individual function calls):
    base_url: string, containing the base url of canvas server
    token: string, containing the user access token.  Must be set!
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
        with open(expanduser(file),'r') as f:
            token = f.read().rstrip('\n')
    except:
        print("Could not read access token")

def calendar_event_data (course, title, description, start_at, end_at, access_token=None):
    """
    Creates a dict with parameters for calendar event data to be passed to
    `create_calendar_event`. Parameters:
        course: course id, string or int
        title: string, event title
        description: string, detailed event description
        start_at: starting time, in YYYY-MM-DDTHH:MMZZ format
        end_at: ending time, in YYYY-MM-DDTHH:MMZZ format
        access_token: optional access token, if different from global one
    """
    if access_token == None:
        access_token = token
    event_data = {
        'calendar_event[context_code]':'course_{}'.format(course),
        'calendar_event[title]':title,
        'calendar_event[description]':description,
        'calendar_event[start_at]':start_at,
        'calendar_event[end_at]':end_at,
        'access_token':access_token
    }
    return event_data

def create_calendar_event (event_data, base=None):
    "Post an event described by `event_data` dict to a calendar"
    if base == None:
        base = base_url
    return requests.post(base + 'api/v1/calendar_events.json', params = event_data)

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

def create_events_from_list(course, list, start, length):
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
    for i,event in enumerate(list):
        if event[0] != "":
            create_calendar_event(
                calendar_event_data(course, event[0], event[1], 
                                    *class_span(classtime,length))
            )
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
    if access_token == None:
        access_token = token
    if base == None:
        base = base_url
    html = markdown.markdown(markdown_body, ['extra'])
    return requests.put(base + 'api/v1/courses/{}'.format(course), 
                        {'access_token':access_token, 'course[syllabus_body]':html})

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
    if access_token == None:
        access_token = token
    if base == None:
        base = base_url
    html = markdown.markdown(markdown_body, ['extra'])
    return requests.post(base + 'api/v1/courses/{}/discussion_topics'.format(course), 
                        {'access_token':access_token, 'title':title,
                         'message':html, 'is_announcement':'1'})

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
    if access_token == None:
        access_token = token
    if base == None:
        base = base_url
    html = markdown.markdown(markdown_body, ['extra'])
    return requests.post(base + 'api/v1/courses/{}/pages'.format(course), 
                        {'access_token':access_token, 'wiki_page[title]':title,
                         'wiki_page[body]':html, 'wiki_page[published]':'1' if
                        published else '0'})
