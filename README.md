# canvas_scripts

Some python scripts for the Canvas learning management system

The Canvas course management system by Instructure has a RESTful API that allows
easy access to a number of features.

These are some scripts that allow an instructor to interact with the system
from the command line, to do things like get a class roster, post an
announcement, create a class syllabus from a source written in markdown, add
links to course navigation that redirect to external websites, etc.

In order to use these scripts, you need an access token from your Canvas
server. For information on how to generate an access token, see 
https://canvas.instructure.com/doc/api/file.oauth.html and https://community.canvaslms.com/docs/DOC-3013.
Place the access token in `~/.canvas/access_token` (make sure you set proper 
permissions for the file to keep others from snooping), or use it directly in
your scripts. If the token is in `~/.canvas/access_token`, you can do this:

    import canvas
    
    canvas.read_access_token()
    #base_url = "https://your.canvas.server/" #default is the SVSU server

    courseid = 666 #replace with your course id number
    
    students = canvas.get_students(courseid)

    print("Student,ID,Section,\nPoints Possible,,,")
    for stud in students:
        print('"{sortable_name}",{id},,'.format(**stud))

to get a csv roster of your course that you can use to upload grades to Canvas
gradebook.

You can find more examples at the [lahvak/canvas_utils](https://github.com/lahvak/canvas_utils) repo.
