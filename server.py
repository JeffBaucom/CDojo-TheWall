# import modules
from flask import Flask, redirect, render_template, flash, session, request
from mysqlconnection import MySQLConnector
import os, binascii
import md5
import re

# initialize global variables
app = Flask(__name__)
app.secret_key = "goldenRoseColorOfADreamIHad"
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9.+_-]+@[a-zA-Z0-9._-]+\.[a-zA-Z]+$')
ALPHA_REGEX = re.compile(r'^[a-zA-Z]+$')
mysql = MySQLConnector(app, 'thewall')

### Rendering Routes
@app.route('/')
def index():
    return render_template('index.html')

# route to get registration form
@app.route('/registration')
def registration():
    return render_template('register.html')

# route to the wall
@app.route('/wall')
def home():
    # prevent unvalidated users from getting to THE WALL
    if not session['uid']:
        return redirect('/')

    # get all messages
    uid = session['uid']
    userDic = mysql.query_db("SELECT CONCAT(users.first_name, ' ', users.last_name) as username FROM users WHERE users.id = :id LIMIT 1 ", {'id': uid})
    user = userDic[0]['username']
    messages = mysql.query_db("SELECT messages.id, messages.message, messages.users_id, messages.created_at, CONCAT(users.first_name, ' ', users.last_name) as username FROM messages JOIN users ON messages.users_id = users.id") 
    # get all comments for all messages
    for message in messages:
        comments = mysql.query_db("SELECT comments.id, comments.comment, comments.users_id, comments.created_at, comments.messages_id, CONCAT(users.first_name, ' ', users.last_name) as username FROM comments JOIN users ON comments.users_id = users.id WHERE comments.messages_id = :mid", {"mid": message['id']}) 
        # attach comments list to message
        if comments:
            message['comments'] = comments
        
    return render_template('home.html',user=user,  messages = messages)

### Login/Validation Routes
# Logout route
@app.route('/logout')
def logout():
    session.pop('uid')
    return redirect('/')

# login validation route
@app.route('/login', methods=['POST'])
def login():
    #retrieve the user
    email = request.form['email']
    password = request.form['password']
    user_query = "SELECT * FROM users WHERE users.email = :email LIMIT 1"
    query_data = {'email': email}
    user = mysql.query_db(user_query, query_data)

    if user:
        #encrypt password
        encrypted_password = md5.new(password + user[0]['salt']).hexdigest()
        if user[0]['password'] == encrypted_password:
            #send validated user to the wall
            session['uid'] = user[0]['id']
            return redirect('/wall')
        else:
            #send invalid login back with error flash
            flash('Incorrect username or password', 'error')
            return redirect('/')
    else:
        flash('Incorrect username or password', 'error')
        return redirect('/')

# registration route
@app.route('/register', methods=['POST'])
def register_user():
    #collect form data
    email = request.form['email']
    firstName = request.form['first_name']
    lastName = request.form['last_name']
    password = request.form['password']
    confirm = request.form['confirm_password']
    errors = []
    
    # Validate Email
    if not EMAIL_REGEX.match(email):
        errors.append('Invalid Email Address')

    # Validate Name
    if (len(firstName) < 2) or (len(lastName) < 2):
        errors.append('First and Last Name must be at least 2 characters')

    if (not ALPHA_REGEX.match(firstName)) or (not ALPHA_REGEX.match(lastName)):
        errors.append('First and Last Name cannot contain numbers or symbols')

    # Password validation
    if len(password) < 8:
        errors.append('Password must be at least 8 characters')

    # Check confirm and password match
    if password != confirm:
        errors.append('Password and Confirm Password must match')
    
    # Check email for duplicates
    if not errors:
        dupes = mysql.query_db("SELECT * FROM users WHERE email = :email", {'email': email})
        if dupes:
            errors.append('This Email has already been registered')

    #attach errors to flash
    if errors:
        for error in errors:
            flash(error, 'error')
        return redirect('/registration')

    #Hash password and insert
    salt = binascii.b2a_hex(os.urandom(15))
    hashed_pw = md5.new(password + salt).hexdigest()
    insert_query = "INSERT INTO users (first_name, last_name, email, password, salt, created_at, updated_at) VALUES (:first_name, :last_name, :email, :password, :salt, NOW(), NOW())"
    query_data = {'first_name': firstName, 'last_name': lastName, 'email': email, 'password': hashed_pw, 'salt': salt}
    mysql.query_db(insert_query, query_data)
    
    # Display successful message
    flash("Successfully Registered, please log in:", 'success')
    return redirect('/')

# route to post a message
@app.route('/message', methods=['POST'])
def create_message():
    message = request.form['message_text']

    #check message validity
    if len(message) < 1:
        flash("Message cannot be blank", "message")
        return redirect('/wall')
    elif (len(message) > 1) and (session['uid']):
        #insert message
        user = session['uid']
        query = "INSERT INTO messages (users_id, message, created_at, updated_at) VALUES (:uid, :message, NOW(), NOW())"
        data = {'uid': user, 'message': message}
        returnval = mysql.query_db(query, data)

        #redirect to the message 
        url = '/wall#' + str(returnval)
        return redirect(url)

@app.route('/comment', methods=['POST'])
def create_comment():
    comment = request.form['comment_text']
    message_id = request.form['message_id']
    uid = session['uid']

    #check comment validity
    if len(comment) < 1:
        session['message_id'] = int(message_id)
        print session['message_id']
        #flash error
        flash("Comment cannot be blank", "comment")
        url = '/wall#' + str(message_id)
        return redirect(url)
    elif (len(comment) > 1) and (session['uid']):
        #insert comment
        query = "INSERT INTO comments (users_id, messages_id, comment, created_at, updated_at) VALUES (:uid, :mid, :comment, NOW(), NOW())"
        data = {'uid': uid, 'mid': message_id, 'comment': comment}
        returnval = mysql.query_db(query, data)
        #redirect to new comment
        url = '/wall#' + str(message_id) + "+" + str(returnval)
        return redirect(url)

# route to delete a message
@app.route('/delete/message', methods=['POST'])
def delete_message():
    commentQuery = "DELETE FROM comments WHERE comments.messages_id = :id"
    cData = {'id': request.form['message_id']}
    mysql.query_db(commentQuery, cData)
    messageQuery = "DELETE FROM messages WHERE messages.id=:id"
    mData = {'id': request.form['message_id'] }
    mysql.query_db(messageQuery, mData)
    #redirect and flash success
    flash("Message Deleted", "success")
    return redirect('/wall')

# route to delete a comment
@app.route('/delete/comment', methods=['POST'])
def delete_comment():
    commentQuery = "DELETE FROM comments WHERE comments.id = :id"
    cData = {'id': request.form['comment_id']}
    mysql.query_db(commentQuery, cData)
    #flash success message
    flash("Comment Deleted", "comment-success")
    message_id = request.form['message_id']
    session['message_id'] = int(message_id)
    #redirect to comment
    url = '/wall#' +str(message_id)
    return redirect(url)
app.run(debug=True)
