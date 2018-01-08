#-*- coding:utf-8 -*-
import datetime

from flask import render_template, request, jsonify, redirect, url_for
from flask_login import current_user, login_user, logout_user, login_required 
from flask_mail import Message

from itsdangerous import URLSafeTimedSerializer

from pdglig.graphdb_interface import UserLoginNotFoundError
from pdglig.graphdb_neo4j.user import User

from app import app, graphdb, mail, bcrypt, hash_pass



infos = {
            "desc" : "user api",
            "version" : "0.2dev"
        }

PADAGRAPH_HOST = app.config["PADAGRAPH_HOST"]

INVITATION_EMAIL = app.config['INVITATION_EMAIL']
ACCOUNT_CREATION_NEEDS_INVITATION = app.config.get("ACCOUNT_CREATION_NEEDS_INVITATION", True) 
AUTH_TOKEN_MAX_AGE = app.config.get("AUTH_TOKEN_MAX_AGE", 30* 24*3600) #  default 30 days
RECOVERY_TOKEN_MAX_AGE = app.config.get("AUTH_TOKEN_MAX_AGE", 24*3600) #  default 30 days

USER_ACCOUNT_LIMIT = app.config['USER_ACCOUNT_LIMIT']

serialiser = URLSafeTimedSerializer(app.config['SECRET_KEY'])




class PdgUser:

    def __init__(self, uuid, username, email, password=None, active=False):
        self.uuid = uuid
        self.email = email
        self.username = username
        self.password = password
        self.active = active
        self._verified = False


    @staticmethod     
    def create(login, email, password):
        return graphdb.create_user(login, email, hash_pass(password), False  )

    
    @staticmethod     
    def activate(email):
        """ will mark this user as active
        user.is_active()
        > True
        """    
        
        user = User.get_by_email(graphdb.db, email)
        user.activate()
        return PdgUser.get_by_email(email)
        
    @staticmethod     
    def has_username(username):
        try :
            if username is not None:        
                u = User.get_by_login(graphdb.db, username)
                return True
        except :
            return False
            
    @staticmethod     
    def has_email(email):
        try :
            if email is not None:        
                u = User.get_by_email(graphdb.db, email)
                return True
        except :
            return False
            
    @staticmethod     
    def get(username):
        user = None
        if username is not None:        
            
            u = User.get_by_login(graphdb.db, username)
            if u:
                user = PdgUser(u.node['uuid'],
                               u.node['username'],
                               u.node['email'],
                               u.node['password'],
                               u.node['active'],
                              )
        return user
        
        #raise UserLoginNotFoundError('login: %s' % login)

    @staticmethod     
    def get_by_email(email):
        user = None
        if email is not None:        
            
            u = User.get_by_email(graphdb.db, email)
            if u:
                user = PdgUser(u.node['uuid'],
                               u.node['username'],
                               u.node['email'],
                               u.node['password'], # may we return **** ?
                               u.node['active'],
                              )
        return user
        
        #raise UserLoginNotFoundError('login: %s' % login)


    @staticmethod     
    def authenticate(email, password, hashed=False):
        """ get user by username, verify password if any given
            return User if username psswd match
        """
        user = PdgUser.get_by_email(email)

        if user and user.is_active():
            if user.verify_password(password, hashed=hashed):
                return user

        return None

    @staticmethod     
    def change_password( email, password):
        u = User.get_by_email(graphdb.db, email)
        hash_password = hash_pass(password)
        u.update_password(hash_password)
        return True

    @staticmethod
    def from_token(token):
        """ authenticate a user using encrypted token """
        
        try :
            email, password  = serialiser.loads(token,max_age=AUTH_TOKEN_MAX_AGE)
            user = PdgUser.get_by_email(email)
            user.verify_password(password, hashed=True)
            
            if user and user.is_active() and user.is_authenticated(): 
                return user
        except:
            raise
            return None

        return  None

    def verify_password(self, password, hashed=True ):
        if hashed:
            self._verified = self.password is not None and self.password == password
        else:
            self._verified = bcrypt.check_password_hash(self.password, password)

        # TODO raise password exception
        
        return self._verified
        
        
    def get_id(self):
        return unicode(self.email)

    def get_auth_token(self):
        """
            return a timed serialized token
            ( email, password )
            time : token expiration
            email: user identificatiob
            password : prevent token login when password is changed
            
        """
        # [email, password]
        data = (self.email, self.password)
        return serialiser.dumps(data)
        
    def __str__(self):
        return  ",".join(( self.username, ))
        
    def is_authenticated(self): 
        return self._verified
 
    def is_active(self):
        return self.active
 
    def is_anonymous(self):
        return False

    def as_dict(self):
        return { 'name': self.username,
                 'active': self.active
               }

from flask_wtf import Form
from wtforms import StringField, BooleanField,  PasswordField
from wtforms.validators import Required, Email, EqualTo


class EmailExistsValidationError(Exception):
    def __init__(self, message, user):
        super(EmailExistsValidationError, self).__init__(message)
        self.user = user

def handleEmailExistsValidationError(err):
    if err.user : #and not err.user.is_active():
        
        email = err.user.email
        token = serialiser.dumps(("activation", email))

        return render_template('create_account.html' ,
                                step="email-in-use",
                                token=token,
                                email=email,
                                username = err.user.username,
                                activ = err.user.is_active() )



class InvitationForm(Form):
    email = StringField('email', [Required(), Email()], default="")
    invite = BooleanField('invite', [Required()], default="")

    def validate(self):
        rv = Form.validate(self)
        if rv:
            user =  PdgUser.get_by_email(self.email.data)
            if user :
                message = 'An account exists with this email'
                raise EmailExistsValidationError(message, user)
        return rv  

class CreateUserForm(Form):
    invitation = StringField('invitation', [Required()] if ACCOUNT_CREATION_NEEDS_INVITATION  else [], default="")
    username = StringField('username', [Required()], default="")
    email = StringField('email', [Required(), Email()], default="")
    password = PasswordField('New Password', [Required(), EqualTo('confirm', message='Passwords must match')])
    confirm  = PasswordField('Repeat Password', [Required()])


    def __init__(self, *args, **kwargs):
        Form.__init__(self, *args, **kwargs)

    def validate(self):
        rv = Form.validate(self)

        # parse invitation token
        invitation = self.invitation.data
        email = ""

        try :
            if ACCOUNT_CREATION_NEEDS_INVITATION :
                seed, email = serialiser.loads(invitation)

                if seed != "invitation":
                    raise ValueError("")
            
            if self.email.data == "":
                self.email.data = email
                
        except Exception as err:
            self.invitation.errors.append('Wrong token' + err.message)
            return False

        if rv == False : return False

        rv = self.email.validate(email)
        
        # uniqness
        if PdgUser.has_username(self.username.data):
            self.username.errors.append('Username already taken')
            rv = False
            
        user =  PdgUser.get_by_email(self.email.data)
        if user :
            message = 'An account exists with this email'
            raise EmailExistsValidationError(message, user)

         # passwrd complexity
        if len(self.password.data) < 6:
            self.password.errors.append('Password length must be at least 6 charaters')
            rv = False
        
        return rv

        
class UserAccountLimitException(Exception):
    def __init__(self):
        super(Exception, self).__init__("Maximum user account %s" % USER_ACCOUNT_LIMIT)

def handleUserAccountLimitException(err):
    return render_template(
                'create_account.html' ,
                step="user-account-limit",
                count=USER_ACCOUNT_LIMIT,
            )

class EmailNotExistsAccountError(Exception):
    def __init__(self, message, email):
        super(EmailNotExistsAccountError, self).__init__(message)
        self.email = email

def handleEmailNotExistsAccountError(err):
    return render_template(
                'account-recovery.html' ,
                step="email-not-in-use",
                email=err.email,
            )

class RecoveryEmailForm(Form):
    email = StringField('email', [Required(), Email()], default="")

    def validate(self):
        rv = Form.validate(self)
        
        if rv:
            email = self.email.data
            user =  PdgUser.get_by_email(email)
            
            if user is None :
                message = 'No account exists with this email'
                raise EmailNotExistsAccountError(message, email)
        return rv
    
class RecoveryPasswordForm(Form):
    password = PasswordField('New Password', [Required(), EqualTo('confirm', message='Passwords must match')])
    confirm  = PasswordField('Repeat Password', [Required()])
    token = StringField('token', [Required()], default="")
    
    def  validate(self):
        rv = Form.validate(self)

        # passwrd complexity
        if len(self.password.data) < 6:
            self.password.errors.append('Password length must be at least 6 charaters')
            rv = False
        return rv

class SendMailError(Exception):
    def __init__(self, email, error):
        super(SendMailError, self).__init__("can't send email to %s" % email)
        self.email = email
        self.error = error
        

def handleSendMailError(err):
    return render_template(
                'create_account.html' ,
                step="cant-send-email",
                email=err.email,
                
            )

def noreply_send(subject, to, body):
    try:
        message = Message(sender = ( "padagraph.io", "noreply@padagraph.io" ))
        message.recipients = [to]
        message.body = body
        message.subject = subject
        print "sending message", subject
        mail.send(message)
    except Exception as err:
        raise SendMailError(to, err)

def send_invitation_link(email):
    
    token = serialiser.dumps(( "invitation", email ))
    url = "%s/account/create-account/%s" % (PADAGRAPH_HOST, token)

    subject = "%s // Invitation" % PADAGRAPH_HOST[7:]
    body   = """
        This address requested an invitation to join padagraph.io:
          %s

        Follow this link to create a new account
          %s
    """% (email, url)

    send_to = email
   
    noreply_send(subject, send_to, body.replace("    ", ""))


def send_activation_link(email):
    
    token = serialiser.dumps(("activation", email ))
    url = "%s/account/activate-account/%s" % (PADAGRAPH_HOST, token)
    subject = "%s // Activate your account" % PADAGRAPH_HOST[7:]

    body   = """
        Thank you for signing up into padagraph.io.

        To get started, please activate your account by clicking on the link below (you may also copy and paste the link into your browser's address bar).

        %s

        If you didn't request this, you don't need to do anything; you won't receive any more email from us. Please do not reply to this e-mail;
        
    """ % url
    
    noreply_send(subject, email, body.replace("    ", ""))


def send_password_recovery_link(email, hashed_password ):
    
    token =  serialiser.dumps(("recovery", email, hashed_password  ))
    
    url = "%s/account/change-password/%s" % (PADAGRAPH_HOST, token)
    subject = "%s // Reset your password" % PADAGRAPH_HOST[7:]

    body   = """
        You recently requested a password reset.
         
        To change your password, click here or paste the following link into your browser:  

        %s
        
        The link will expire in 24 hours.

        If you didn't request this, you don't need to do anything; you won't receive any more email from us. Please do not reply to this e-mail;
        
    """ % url
    
    noreply_send(subject, email, body.replace("    ", ""))
    


def authenticate_user(request):
    if request.method == 'POST':

        username = request.form.get('username', None )
        email = request.form.get('email', None )
        password = request.form.get('password', None )

        if request.json: 
            username = request.json.get('username', None )
            email = request.json.get('email', None )
            password = request.json.get('password', None )
                    
        return PdgUser.authenticate(email, password, hashed=False)

    elif request.method == 'GET': 
        email = request.args['email']
        password = request.args['password']
        return PdgUser.authenticate(email, password, hashed=False)
        

def users_api(name):
    """ user authentification api """
    from app import login_manager
    
    from reliure.web import ReliureAPI

    api = ReliureAPI(name, expose_route = False)
    
    PADAGRAPH_HOST = app.config["PADAGRAPH_HOST"]

    @api.route("/about", methods=['GET', 'POST'])
    def about():
        return jsonify( infos )


    # === auth ====

    @api.route("/authenticate", methods=['GET', 'POST'])
    def auth():
        user = authenticate_user(request)
            
        if user:
            return jsonify({
                 'logged' : True,
                 'user' : user.as_dict(),
                 'token': user.get_auth_token(),
                })

        return "login failed", 401
    
    @api.route("/me", methods=['GET'])
    @login_required
    def me():
        user = current_user
        return jsonify( user.as_dict() )
    
    @api.route("/me/generate_auth_token", methods=['GET'])
    @login_required
    def generate_auth_token():
        user = current_user
        return jsonify({    'user' : user.as_dict(),
                            'token': user.get_auth_token(),
                        })
    
    @api.route("/login", methods=['GET', 'POST'])
    def login():
        logged = False

        print ">>>>>>> login"

        
        user = authenticate_user(request)

        print request, user
        
        if user:
            logged = True
            login_user(user)
            url = request.args.get('redirect', None )
            if url :
                return redirect(url)

        return jsonify({ 'logged': logged,
                         'username':user.username if logged else "" })
    
    @api.route("/logout", methods=['GET', 'POST'])
    def logout():
        print "req.cookie", request.cookies
        try:
            logout_user()
        finally:
            pass
        
        if request.method == "GET":
            resp =  redirect('/')
        else:
            resp = jsonify({ 'logged': False })


        resp.set_cookie('session', '', expires=0)
        resp.set_cookie('gggg', 'bla', expires=23330)
        return resp    
        
    # === create account ===

    @api.route("/invitation", methods=['POST'])
    def invite(invitation=None):
        
        # validate token
        form = InvitationForm()

        if form.validate():

            send_invitation_link(form.email.data)
            
            return render_template('create_account.html' , step="invitation-send")            

        return redirect('/?invalid=1')


    @api.route("/create-account", methods=['POST', 'GET'])
    @api.route("/create-account/<string:invitation>", methods=['GET'])
    def create_account(invitation=None):

        step = "create"
        has_error = False

        if USER_ACCOUNT_LIMIT > 0:
            if graphdb.get_users_count() >= USER_ACCOUNT_LIMIT:
                raise UserAccountLimitException()

        form = CreateUserForm()

        if request.method == "GET":
            form.invitation.data = invitation

            if not form.validate():
                print form.invitation.errors
                if len(form.invitation.errors):
                    return render_template('create_account.html' , step="invitation-invalid")            

        elif request.method == "POST":
            if form.validate():

                # create user
                username = form.username.data
                email = form.email.data
                password = form.password.data
                
                login = PdgUser.create( username, email, password )

                send_activation_link(email)

                return render_template('create_account.html' , step="validate", form=form )

            else:
                has_error = True

                if len(form.invitation.errors):
                    
                    return render_template('create_account.html' , step="invitation-invalid" )

        return render_template('create_account.html', step=step, form=form, has_error=has_error)


    @api.route("/resend-validation/<string:token>", methods=['GET'])
    def resend_validation(token=None):

        # validate token
        try :
            
            seed, email = serialiser.loads(token)
            if seed != "activation":
                raise ValueError()

            user = PdgUser.get_by_email(email)
            send_activation_link(email)
            return render_template('create_account.html' ,
                                   step="validation-resent",
                                   username=user.username,
                                   email=email )

        except :
            return render_template('create_account.html' , step="token-invalid" )
            


    @api.route("/activate-account/<string:token>", methods=['GET'])
    def activate_account(token=None):

        # validate token
        try :
            
            seed, email = serialiser.loads(token)
            
            if seed != "activation":
                raise ValueError("wrong token")
                
            user = PdgUser.activate(email)
            return render_template('create_account.html' , step="active", username=user.username )
            
        except :
            return render_template('create_account.html' , step="token-invalid" )
            


    # === / password recovery ===

    @api.route("/password-recovery", methods=['GET', 'POST'])
    def get_recovery():

        form = RecoveryEmailForm()
        
        if request.method == "POST" and form.validate():
            
            # send email recovery 
            try :
                email = form.email.data
                if PdgUser.has_email(email):
                    user = PdgUser.get_by_email(email)
                    send_password_recovery_link(email, user.password )
                return render_template('account-recovery.html', step="email-sent", email= email )
            except :
                raise
                return render_template('account-recovery.html' , step="token-invalid" )

        return render_template('account-recovery.html', step="email-form")
    
    @api.route("/change-password", methods=['POST'])
    @api.route("/change-password/<string:token>", methods=['GET'])
    def post_recovery(token=None):
        form =  RecoveryPasswordForm()

        if request.method == "POST":
            token = form.token.data

        try :
            # validate 24h token
            
            seed, email, pwd = serialiser.loads(token, max_age=RECOVERY_TOKEN_MAX_AGE)

            if seed != "recovery":
                raise ValueError("wrong token, %s" % seed)

            user = PdgUser.get_by_email(email)
            if not user.verify_password(pwd, hashed=True):
                raise ValueError("wrong token, %s" % seed)

            if request.method == "POST":
                if  form.validate():                
                    PdgUser.change_password(email, form.password.data)
                    return render_template('account-recovery.html' , step="password-changed" )
                    
                return render_template('account-recovery.html' , step="password-form", token=token, email=email, has_error=True, errors=form.errors )
        except :
            return render_template('account-recovery.html' , step="token-invalid" )

        return render_template('account-recovery.html' , step="password-form", token=token, has_error=False)
            
        

    @api.route("/u/<string:uid>", methods=['GET'])
    @login_required
    def user(uid):
        """ Get public info for user <user> """
        user = User.get(uid)
        return jsonify( { uuid : user.as_dict() } )



    @api.route("/count", methods=['GET'])
    #@login_required
    def users_count():
        """ Get users count """
        print "count"
        count = graphdb.get_users_count()
        return jsonify( { "count" : count } )


    return api