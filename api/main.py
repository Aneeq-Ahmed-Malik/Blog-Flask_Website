from flask import Flask, render_template, redirect, url_for, flash, abort, request
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from sqlalchemy.exc import IntegrityError
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
from functools import wraps
import smtplib
import os
import datetime as dt


app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("Secret")
app.jinja_env.globals['Year'] = dt.datetime.now().year


ckeditor = CKEditor(app)
bootstrap = Bootstrap5(app)


my_email = os.environ.get("Email")
password = os.environ.get("Pass")

##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("sqlite:///blog.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)


gravatar = Gravatar(app, size=100, rating='g', default='retro', force_default=False,force_lower=False,
                    use_ssl=False, base_url=None)

##CONFIGURE TABLES

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False)
    email = db.Column(db.String(250), nullable=False, unique=True)
    password = db.Column(db.String(250), nullable=False)

    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="author")
    likes = relationship("Like", back_populates="author")

class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)

    author = relationship("User", back_populates="comments")
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    post = relationship("BlogPost", back_populates="comments")
    post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'))


class Like(db.Model):
    __tablename__ = "likes"
    id = db.Column(db.Integer, primary_key=True)

    author = relationship("User", back_populates="likes")
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    post = relationship("BlogPost", back_populates="likes")
    post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'))

class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)

    author = relationship("User", back_populates="posts")
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    comments = relationship("Comment", back_populates="post")
    likes = relationship("Like", back_populates="post")


# with app.app_context():
#     db.create_all()


def admin_only(function):
    @wraps(function)
    def inner(*args, **kwargs):
        post= BlogPost.query.get(kwargs['post_id'])
        if not current_user.is_anonymous :
            if current_user.id == post.author.id:
                return function(*args, **kwargs)

        return abort(403)

    return inner


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts)


@app.route('/register', methods=["POST", "GET"])
def register():
    form = RegisterForm()

    if form.validate_on_submit():
        user = User()
        form.populate_obj(user)
        user.password = generate_password_hash(user.password, salt_length=8)

        try:
            db.session.add(user)
            db.session.commit()
        except IntegrityError:
            flash("That email has already been registered, use another one or Log in instead!", "error")
            return redirect(url_for("register"))

        login_user(user)
        return redirect(url_for("get_all_posts"))

    return render_template("register.html", form=form)


@app.route('/login', methods=["POST", "GET"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.query(User).filter(User.email.like(form.email.data)).first()

        if user == None:
            flash("Incorrect email, please try again!")
            return redirect(url_for("login"))

        if check_password_hash(user.password, form.password.data):
            login_user(user)
            return redirect(url_for("get_all_posts"))
        else:
            flash("Incorrect password, please try again!")
            return redirect(url_for("login"))

    return render_template("login.html", form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["POST", "GET"])
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    form = CommentForm()
    if form.validate_on_submit():
        new_comment = Comment(
            text = form.comment.data,
            author = current_user,
            post = requested_post
        )
        db.session.add(new_comment)
        db.session.commit()
        return redirect(url_for("show_post", post_id=post_id))

    return render_template("post.html", post=requested_post, form=form)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/new-post", methods=["POST", "GET"])
@login_required
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        if new_post.img_url == "":
            new_post.img_url = "https://images.unsplash.com/photo-1586380951230-e6703d9f6833?ixlib=rb-4.0.3&ixid=" \
                               "M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=1374&q=80"

        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, heading="New Post")


@app.route("/edit-post/<int:post_id>", methods=["POST", "GET"])
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data

        if edit_form.img_url.data == "":
            post.img_url = "https://images.unsplash.com/photo-1586380951230-e6703d9f6833?ixlib=rb-4.0.3&ixid=" \
                               "M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=1374&q=80"

        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form, heading="Edit Post")


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/like")
def like():
    post_id = request.args.get("post_id")
    requested_post = BlogPost.query.get(post_id)
    new_like = Like(
        author=current_user,
        post=requested_post
    )
    db.session.add(new_like)
    db.session.commit()
    return redirect(url_for("show_post", post_id=post_id))


@app.route("/delete-like/<post_id>")
def delete_like(post_id):
    post = BlogPost.query.get(post_id)
    for like in post.likes:
        if like.author_id == current_user.id:
            db.session.delete(like)
            db.session.commit()
            break
    return redirect(url_for("show_post", post_id=post_id))


@app.route("/delete-comment/<comment_id>")
def delete_comment(comment_id):
    comment = Comment.query.get(comment_id)
    post_id = comment.post_id

    db.session.delete(comment)
    db.session.commit()

    return redirect(url_for("show_post", post_id=post_id))


@app.route('/contact', methods=["POST", "GET"])
def contact():
    if request.method == "POST":
        with smtplib.SMTP("smtp.gmail.com", port=587) as connection:
            connection.starttls()
            connection.login(user=my_email, password=password)
            connection.sendmail(
                from_addr=my_email,
                to_addrs="aneeqmalik789@gmail.com",
                msg=f"Subject:New Message\n\nName: {request.form['name']}\nEmail: {request.form['email']}\n"
                    f"Phone: {request.form['phone']}\nMessage: {request.form['message']}"
            )
        return render_template("contact.html", title="Contact", msg=True)
    else:
        return render_template("contact.html", title="Contact", msg=False)



if __name__ == "__main__":
    app.run(debug=True)
