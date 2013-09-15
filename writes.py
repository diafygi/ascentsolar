from pprint import pprint
from urlparse import parse_qsl
import urllib
import json
import string
import random
import re
from uuid import uuid4
from jinja2 import Template
from datetime import date, datetime

#yes, I know that this shits all over PEP8, dealwithit.gif
#yes, I know that a framework like Django would be so much cleaner,
#     but hackathons are for experimenting aren't they? An entire web
#     inventory management system with just standard library, jinja2,
#     and MySQLdb in <24 hours? Look at all the fucks I give.

###########
# Helpers #
###########

def helper_orders(rows):
    results = []
    for row in rows:
        results.append({
            "id": int(row[0]),
            "cost": float(row[1]),
            "currency": row[2],
            "created": row[3],
            "paid": row[4],
            "fulfilled": row[5],
            "commissioned": row[6],
            "seller": int(row[7]),
            "buyer": int(row[8]),
            "properties": json.loads(row[9]) if row[9] else {},
        })
    return results

def helper_order_products(rows):
    results = []
    for row in rows:
        results.append({
            "id": int(row[0]),
            "order_id": int(row[1]),
            "product_id": int(row[2]),
        })
    return results

def helper_payments(rows):
    results = []
    for row in rows:
        results.append({
            "id": int(row[0]),
            "user_id": int(row[1]),
            "amount": float(row[2]),
            "currency": row[3],
            "created": row[4],
            "order_id": int(row[5]) if row[5] else None,
        })
    return results

def helper_products(rows):
    results = []
    for row in rows:
        results.append({
            "id": int(row[0]),
            "created_by": int(row[1]),
            "current_owner": int(row[2]),
            "properties": json.loads(row[3]) if row[3] else {},
        })
    return results

def helper_sessions(rows):
    results = []
    for row in rows:
        results.append({
            "id": row[0],
            "user": int(row[1]),
        })
    return results

def helper_users(rows):
    results = []
    for row in rows:
        results.append({
            "id": int(row[0]),
            "type": row[1],
            "boss": int(row[2]),
            "login": row[3],
            "password": row[4],
            "properties": json.loads(row[5]) if row[5] else {},
        })
    return results

def helper_req2user(req):
    #parse the cookie
    cookie_raw = req.get("HTTP_COOKIE", "")
    sessionsearch = re.search("session=([a-fA-F0-9]+)", cookie_raw)
    #return no user if no cookie found
    if not sessionsearch:
        return None
    #query for session-to-user relationship
    sessionid = sessionsearch.groups()[0]
    req['cur'].execute("SELECT * FROM solar.session WHERE `id` = %s", sessionid)
    results = helper_sessions(req['cur'].fetchall())
    #return no user if no session found
    if not results:
        return None
    #get user dictionary from user id
    userid = results[0]['user']
    req['cur'].execute("SELECT * FROM solar.user WHERE `id` = %s", userid)
    return helper_users(req['cur'].fetchall())[0]


#########
# Pages #
#########
def login(req):
    if req['REQUEST_METHOD'] == "GET":
        user = helper_req2user(req)
        data = dict(parse_qsl(req['QUERY_STRING']))
        tmpl = Template("""
            <html>
            <head><title>Login</title></head>
            <body>
                <form action="." method="post">
                <input type="hidden" name="next" value="{% if data.next %}{{ data.next|escape }}{% endif %}"/>
                login: <input name="login" value="{% if data.login %}{{ data.login|escape }}{% endif %}"/><br/>
                password: <input type="password" name="password"/><br/>
                <input type="submit"/>
                {% if data.msg %}<br/>{{ data.msg|escape }}{% endif %}
                </form>
                {% if user %}
                <a href="/product/">My Inventory</a><br/>
                <a href="/order/add/">Add Order</a><br/>
                <a href="/logout/">Logout</a>
                {% endif %}
            </body>
            </html>
        """)
        html = str(tmpl.render(data=data, user=user))
        return "200 OK", [('Content-type', 'text/html')], html
    if req['REQUEST_METHOD'] == "POST":
        #parse post data
        data = dict(parse_qsl(req['wsgi.input'].read(int(req.get('CONTENT_LENGTH', '0')))))
        next = urllib.unquote(data.get("next", "/"))
        #didn't find login key
        if not data.get("login"):
            return "302 Found", [('Location', '/?msg=LoginNotFound')], ""
        #lookup login
        cur = req['cur']
        cur.execute("SELECT * FROM solar.user WHERE `login` = %s", data['login'])
        results = helper_users(cur.fetchall())
        #didn't find login, redirect home
        if not results:
            return "302 Found", [('Location', '/?msg=LoginNotFound')], ""
        elif len(results) > 1:
            return "302 Found", [('Location', '/?msg=MultiLoginError')], ""
        #one user returned
        else:
            #check password
            if results[0]['password'] != data.get("password", ""):
                return "302 Found", [('Location', '/?msg=BadPassword&login={}'.format(data['login']))], ""
            #password fine, so create new session
            userid = results[0]['id']
            sessionid = uuid4().hex
            cur.execute("INSERT INTO solar.session (id, user) VALUES (%s, %s)", (sessionid, userid))
            return "302 Found", [
                ('Location', next),
                ('Set-Cookie', 'session={}; Path=/; HttpOnly'.format(sessionid)),
            ], ""

def logout(req):
    return "302 Found", [
        ('Location', '/?msg=LoggedOut'),
        ('Set-Cookie', 'session=; Path=/; HttpOnly'),
    ], ""

def manufacturer_id_edit(req):
    #require login
    user = helper_req2user(req)
    if not user:
        return "302 Found", [('Location', '/?next={}'.format(urllib.quote(req['PATH_INFO'])))], ""
    #validate permissions (admins only)
    if not user['type'] == "admin":
        return "302 Found", [('Location', '/?msg=InvalidPermission')], ""
    #get manufacturer to edit
    man_id = int(re.search("/manufacturer/([0-9]+)/edit/", req['PATH_INFO']).groups()[0])
    cur = req['cur']
    cur.execute("SELECT * FROM solar.user WHERE `id` = %s", man_id)
    results = helper_users(cur.fetchall())
    if not results:
        return "302 Found", [('Location', '/?msg=MissingManufacturer')], ""
    man = results[0]
    #show form if GET method
    if req['REQUEST_METHOD'] == "GET":
        data = dict(parse_qsl(req['QUERY_STRING']))
        tmpl = Template("""
            <html>
            <head><title>Edit Manufacturer {{ man.id }}</title></head>
            <body>
                <form action="." method="post">
                name: <input name="name" value="{% if man.properties.name %}{{ man.properties.name|escape }}{% endif %}"/><br/>
                location: <input name="location" value="{% if man.properties.location %}{{ man.properties.location|escape }}{% endif %}"/><br/>
                login: <input name="login" value="{% if man.login %}{{ man.login|escape }}{% endif %}"/><br/>
                password: <input type="password" name="password" value="{% if man.password %}{{ man.password|escape }}{% endif %}"/><br/>
                created: {{ man.properties.created|escape }}<br/>
                <input type="submit"/>
                {% if msg %}<br/>{{ msg|escape }}{% endif %}
                </form>
            </body>
            </html>
        """)
        html = str(tmpl.render(msg=data.get("msg"), man=man))
        return "200 OK", [('Content-type', 'text/html')], html
    #process form if POST method
    if req['REQUEST_METHOD'] == "POST":
        #parse post data
        data = dict(parse_qsl(req['wsgi.input'].read(int(req.get('CONTENT_LENGTH', '0')))))
        #validate form
        if not (data.get("name") and data.get("location") and data.get("login") and data.get("password")):
            return "302 Found", [('Location', '?msg=MissingFields')], ""
        #create json string for properties
        man['properties']['name'] = data['name']
        man['properties']['location'] = data['location']
        props = json.dumps(man['properties'])
        #update field in db
        cur.execute("UPDATE solar.user SET login=%s, password=%s, properties=%s WHERE id=%s",
            (data['login'], data['password'], props, man['id']))
        return "302 Found", [('Location', '/manufacturer/{}/edit/?msg=Updated'.format(man['id']))], ""

def manufacturer_add(req):
    #require login
    user = helper_req2user(req)
    if not user:
        return "302 Found", [('Location', '/?next={}'.format(urllib.quote(req['PATH_INFO'])))], ""
    #validate permissions (admins only)
    if not user['type'] == "admin":
        return "302 Found", [('Location', '/?msg=InvalidPermission')], ""
    #show form if GET method
    if req['REQUEST_METHOD'] == "GET":
        data = dict(parse_qsl(req['QUERY_STRING']))
        tmpl = Template("""
            <html>
            <head><title>Add Manufacturer</title></head>
            <body>
                <form action="." method="post">
                name: <input name="name" value="{% if data.name %}{{ data.name|escape }}{% endif %}"/><br/>
                location: <input name="location" value="{% if data.location %}{{ data.location|escape }}{% endif %}"/><br/>
                login: <input name="login" value="{% if data.login %}{{ data.login|escape }}{% endif %}"/><br/>
                password: <input type="password" name="password" value="{% if data.password %}{{ data.password|escape }}{% endif %}"/><br/>
                <input type="submit"/>
                {% if data.msg %}<br/>{{ data.msg|escape }}{% endif %}
                </form>
            </body>
            </html>
        """)
        html = str(tmpl.render(data=data))
        return "200 OK", [('Content-type', 'text/html')], html
    #process form if POST method
    if req['REQUEST_METHOD'] == "POST":
        #parse post data
        data = dict(parse_qsl(req['wsgi.input'].read(int(req.get('CONTENT_LENGTH', '0')))))
        #validate form
        if not (data.get("name") and data.get("location") and data.get("login") and data.get("password")):
            return "302 Found", [('Location', '?msg=MissingFields')], ""
        #create json string for properties
        props = json.dumps({
            "name": data['name'],
            "location": data['location'],
            "created": date.today().strftime("%Y-%m-%d"),
            "picture": "none",
        })
        #insert field in db
        cur = req['cur']
        cur.execute("INSERT INTO solar.user (type, boss, login, password, properties) VALUES (%s, %s, %s, %s, %s)",
            ("manufacturer", 0, data['login'], data['password'], props))
        cur.execute("SELECT LAST_INSERT_ID()")
        results = cur.fetchall()
        man_id = int(results[0][0])
        return "302 Found", [('Location', '/manufacturer/{}/edit/'.format(man_id))], ""

def product_id_edit(req):
    #require login
    user = helper_req2user(req)
    if not user:
        return "302 Found", [('Location', '/?next={}'.format(urllib.quote(req['PATH_INFO'])))], ""
    #get product to edit
    prod_id = int(re.search("/product/([0-9]+)/edit/", req['PATH_INFO']).groups()[0])
    cur = req['cur']
    cur.execute("SELECT * FROM solar.product WHERE `id` = %s", prod_id)
    results = helper_products(cur.fetchall())
    if not results:
        return "302 Found", [('Location', '/?msg=MissingProduct')], ""
    prod = results[0]
    #get creator
    cur.execute("SELECT * FROM solar.user WHERE `id` = %s", prod['created_by'])
    creator = helper_users(cur.fetchall())[0]
    #validate permissions (admins and creator lackies only)
    if user['type'] != "admin":
        if user['type'] not in ["manufacturer", "distributor"]:
            return "302 Found", [('Location', '/?msg=InvalidPermission1')], ""
        if not (creator['id'] == user['id'] or creator['id'] == user['boss']):
            return "302 Found", [('Location', '/?msg=InvalidPermission2')], ""
    #show form if GET method
    if req['REQUEST_METHOD'] == "GET":
        data = dict(parse_qsl(req['QUERY_STRING']))
        #get owner dictionaries
        cur.execute("SELECT * FROM solar.user WHERE `id` = %s", prod['current_owner'])
        owner = helper_users(cur.fetchall())[0]
        #render form
        tmpl = Template("""
            <html>
            <head><title>Edit Product {{ prod.id }}</title></head>
            <body>
                <form action="." method="post">
                {% if user.type != "distributor" %}
                    name: <input name="name" value="{% if prod.properties.name %}{{ prod.properties.name|escape }}{% endif %}"/><br/>
                {% else %}
                    <input type="hidden" name="name" value="{{ prod.properties.name|escape }}"/>
                    name: {{ prod.properties.name|escape }}<br/>
                {% endif %}
                {% if user.type == "admin" %}
                    created by: <input name="created_by" value="{% if prod.created_by %}{{ prod.created_by|escape }}{% endif %}"/>
                    ({{ creator.properties.name }})<br/>
                {% else %}
                    <input type="hidden" name="created_by" value="{% if prod.created_by %}{{ prod.created_by|escape }}{% endif %}"/>
                    created by: {{ creator.id }} ({{ creator.properties.name }})<br/>
                {% endif %}
                current owner: <input name="current_owner" value="{% if prod.current_owner %}{{ prod.current_owner|escape }}{% endif %}"/>
                ({{ owner.properties.name }})<br/>
                created on: {{ prod.properties.created|escape }}<br/>
                <input type="submit"/>
                {% if msg %}<br/>{{ msg|escape }}{% endif %}
                </form>
            </body>
            </html>
        """)
        html = str(tmpl.render(msg=data.get("msg"), prod=prod, creator=creator, owner=owner, user=user))
        return "200 OK", [('Content-type', 'text/html')], html
    #process form if POST method
    if req['REQUEST_METHOD'] == "POST":
        #parse post data
        data = dict(parse_qsl(req['wsgi.input'].read(int(req.get('CONTENT_LENGTH', '0')))))
        #validate form
        if not (data.get("name") and data.get("created_by") and data.get("current_owner")):
            return "302 Found", [('Location', '?msg=MissingFields')], ""
        #create json string for properties
        prod['properties']['name'] = data['name']
        props = json.dumps(prod['properties'])
        #update field in db
        cur.execute("UPDATE solar.product SET created_by=%s, current_owner=%s, properties=%s WHERE id=%s",
            (data['created_by'], data['current_owner'], props, prod['id']))
        return "302 Found", [('Location', '/product/{}/edit/?msg=Updated'.format(prod['id']))], ""

def product_add(req):
    #require login
    user = helper_req2user(req)
    if not user:
        return "302 Found", [('Location', '/?next={}'.format(urllib.quote(req['PATH_INFO'])))], ""
    #validate permissions (admins and manufacturers only)
    if user['type'] not in ["admin", "manufacturer"]:
        return "302 Found", [('Location', '/?msg=InvalidPermission')], ""
    #show form if GET method
    if req['REQUEST_METHOD'] == "GET":
        data = dict(parse_qsl(req['QUERY_STRING']))
        tmpl = Template("""
            <html>
            <head><title>Add Product</title></head>
            <body>
                <form action="." method="post">
                name: <input name="name" value="{% if data.name %}{{ data.name|escape }}{% endif %}"/><br/>
                {% if user.type == "admin" %}
                    created by: <input name="created_by" value="{% if user.id %}{{ user.id|escape }}{% endif %}"/><br/>
                {% else %}
                    <input type="hidden" name="created_by" value="{{ user.id|escape }}"/>
                    created by: {{ user.id }} ({{ user.properties.name }})<br/>
                {% endif %}
                current_owner: <input name="current_owner" value="{% if data.current_owner %}{{ data.current_owner|escape }}{% else %}{{ user.id|escape }}{% endif %}"/><br/>
                <input type="submit"/>
                {% if data.msg %}<br/>{{ data.msg|escape }}{% endif %}
                </form>
            </body>
            </html>
        """)
        html = str(tmpl.render(data=data, user=user))
        return "200 OK", [('Content-type', 'text/html')], html
    #process form if POST method
    if req['REQUEST_METHOD'] == "POST":
        #parse post data
        data = dict(parse_qsl(req['wsgi.input'].read(int(req.get('CONTENT_LENGTH', '0')))))
        #validate form
        if not (data.get("name") and data.get("created_by") and data.get("current_owner")):
            return "302 Found", [('Location', '?msg=MissingFields')], ""
        #create json string for properties
        props = json.dumps({
            "name": data['name'],
            "created": date.today().strftime("%Y-%m-%d"),
        })
        #insert field in db
        cur = req['cur']
        cur.execute("INSERT INTO solar.product (created_by, current_owner, properties) VALUES (%s, %s, %s)",
            (data['created_by'], data['current_owner'], props))
        cur.execute("SELECT LAST_INSERT_ID()")
        results = cur.fetchall()
        prod_id = int(results[0][0])
        return "302 Found", [('Location', '/product/{}/edit/'.format(prod_id))], ""

def product_mass_assign(req):
    return "200 OK", [('Content-type', 'text/html')], "<html><body>product_mass_assign</body></html>"

def distributor_id_edit(req):
    #require login
    user = helper_req2user(req)
    if not user:
        return "302 Found", [('Location', '/?next={}'.format(urllib.quote(req['PATH_INFO'])))], ""
    #get distributor to edit
    dist_id = int(re.search("/distributor/([0-9]+)/edit/", req['PATH_INFO']).groups()[0])
    cur = req['cur']
    cur.execute("SELECT * FROM solar.user WHERE `id` = %s", dist_id)
    results = helper_users(cur.fetchall())
    if not results:
        return "302 Found", [('Location', '/?msg=MissingDistributor')], ""
    dist = results[0]
    #validate permissions (admins bosses only)
    if user['type'] != "admin":
        if not (user['type'] == "manufacturer" and user['id'] == dist['boss']):
            return "302 Found", [('Location', '/?msg=InvalidPermission1')], ""
    #show form if GET method
    if req['REQUEST_METHOD'] == "GET":
        data = dict(parse_qsl(req['QUERY_STRING']))
        #get boss dictionary
        cur.execute("SELECT * FROM solar.user WHERE `id` = %s", dist['boss'])
        boss = helper_users(cur.fetchall())[0]
        #render form
        tmpl = Template("""
            <html>
            <head><title>Edit Distributor {{ dist.id }}</title></head>
            <body>
                <form action="." method="post">
                name: <input name="name" value="{% if dist.properties.name %}{{ dist.properties.name|escape }}{% endif %}"/><br/>
                {% if user.type == "admin" %}
                    boss: <input name="boss" value="{% if dist.boss %}{{ dist.boss|escape }}{% endif %}"/>
                    ({{ boss.properties.name }})<br/>
                {% else %}
                    <input type="hidden" name="boss" value="{{ dist.boss|escape }}"/>
                    boss: {{ dist.boss|escape }} ({{ boss.properties.name }})<br/>
                {% endif %}
                location: <input name="location" value="{% if dist.properties.location %}{{ dist.properties.location|escape }}{% endif %}"/><br/>
                login: <input name="login" value="{% if dist.login %}{{ dist.login|escape }}{% endif %}"/><br/>
                password: <input type="password" name="password" value="{% if dist.password %}{{ dist.password|escape }}{% endif %}"/><br/>
                created: {{ dist.properties.created|escape }}<br/>
                <input type="submit"/>
                {% if msg %}<br/>{{ msg|escape }}{% endif %}
                </form>
            </body>
            </html>
        """)
        html = str(tmpl.render(msg=data.get("msg"), dist=dist, boss=boss, user=user))
        return "200 OK", [('Content-type', 'text/html')], html
    #process form if POST method
    if req['REQUEST_METHOD'] == "POST":
        #parse post data
        data = dict(parse_qsl(req['wsgi.input'].read(int(req.get('CONTENT_LENGTH', '0')))))
        #validate form
        if not (data.get("name") and data.get("location") and data.get("login") and data.get("password") and data.get("boss")):
            return "302 Found", [('Location', '?msg=MissingFields')], ""
        #create json string for properties
        dist['properties']['name'] = data['name']
        dist['properties']['location'] = data['location']
        props = json.dumps(dist['properties'])
        #update field in db
        cur.execute("UPDATE solar.user SET boss=%s, login=%s, password=%s, properties=%s WHERE id=%s",
            (data['boss'], data['login'], data['password'], props, dist['id']))
        return "302 Found", [('Location', '/distributor/{}/edit/?msg=Updated'.format(dist['id']))], ""

def distributor_add(req):
    cur = req['cur']
    #require login
    user = helper_req2user(req)
    if not user:
        return "302 Found", [('Location', '/?next={}'.format(urllib.quote(req['PATH_INFO'])))], ""
    #validate permissions (admins and manufacturers only)
    if not user['type'] in ["admin", "manufacturer"]:
        return "302 Found", [('Location', '/?msg=InvalidPermission')], ""
    #show form if GET method
    if req['REQUEST_METHOD'] == "GET":
        data = dict(parse_qsl(req['QUERY_STRING']))
        if data.get("user") and user['type'] == "admin":
            cur.execute("SELECT * FROM solar.user WHERE `id` = %s", dist['boss'])
            boss = helper_users(cur.fetchall())[0]
        else:
            boss = user
        #get boss dictionary
        tmpl = Template("""
            <html>
            <head><title>Add Distributor</title></head>
            <body>
                <form action="." method="post">
                name: <input name="name" value="{% if data.name %}{{ data.name|escape }}{% endif %}"/><br/>
                {% if user.type == "admin" %}
                    boss: <input name="boss" value="{{ boss.id }}"/>
                    ({{ boss.properties.name }})<br/>
                {% else %}
                    <input type="hidden" name="boss" value="{{ boss.id|escape }}"/>
                    boss: {{ boss.id|escape }} ({{ boss.properties.name }})<br/>
                {% endif %}
                location: <input name="location" value="{% if data.location %}{{ data.location|escape }}{% endif %}"/><br/>
                login: <input name="login" value="{% if data.login %}{{ data.login|escape }}{% endif %}"/><br/>
                password: <input type="password" name="password" value="{% if data.password %}{{ data.password|escape }}{% endif %}"/><br/>
                <input type="submit"/>
                {% if data.msg %}<br/>{{ data.msg|escape }}{% endif %}
                </form>
            </body>
            </html>
        """)
        html = str(tmpl.render(data=data, user=user, boss=boss))
        return "200 OK", [('Content-type', 'text/html')], html
    #process form if POST method
    if req['REQUEST_METHOD'] == "POST":
        #parse post data
        data = dict(parse_qsl(req['wsgi.input'].read(int(req.get('CONTENT_LENGTH', '0')))))
        #validate form
        if not (data.get("name") and data.get("location") and data.get("login") and data.get("password") and data.get("boss")):
            return "302 Found", [('Location', '?msg=MissingFields')], ""
        #create json string for properties
        props = json.dumps({
            "name": data['name'],
            "location": data['location'],
            "created": date.today().strftime("%Y-%m-%d"),
            "picture": "none",
        })
        #insert field in db
        cur = req['cur']
        cur.execute("INSERT INTO solar.user (type, boss, login, password, properties) VALUES (%s, %s, %s, %s, %s)",
            ("distributor", data['boss'], data['login'], data['password'], props))
        cur.execute("SELECT LAST_INSERT_ID()")
        results = cur.fetchall()
        dist_id = int(results[0][0])
        return "302 Found", [('Location', '/distributor/{}/edit/'.format(dist_id))], ""

def seller_id_edit(req):
    #require login
    user = helper_req2user(req)
    if not user:
        return "302 Found", [('Location', '/?next={}'.format(urllib.quote(req['PATH_INFO'])))], ""
    #get seller to edit
    sell_id = int(re.search("/seller/([0-9]+)/edit/", req['PATH_INFO']).groups()[0])
    cur = req['cur']
    cur.execute("SELECT * FROM solar.user WHERE `id` = %s", sell_id)
    results = helper_users(cur.fetchall())
    if not results:
        return "302 Found", [('Location', '/?msg=MissingDistributor')], ""
    sell = results[0]
    #get boss
    cur.execute("SELECT * FROM solar.user WHERE `id` = %s", sell['boss'])
    boss = helper_users(cur.fetchall())[0]
    #validate permissions (admins and bosses only)
    if user['type'] != "admin":
        if user['type'] not in ["manufacturer", "distributor"]:
            return "302 Found", [('Location', '/?msg=InvalidPermission1')], ""
        #allow if direct boss
        if not (user['type'] == "distributor" and user['id'] == sell['boss']):
            #allow if boss of boss of seller
            if user['id'] != boss['boss']:
                return "302 Found", [('Location', '/?msg=InvalidPermission1')], ""
    #show form if GET method
    if req['REQUEST_METHOD'] == "GET":
        data = dict(parse_qsl(req['QUERY_STRING']))
        #get boss dictionary
        cur.execute("SELECT * FROM solar.user WHERE `id` = %s", sell['boss'])
        boss = helper_users(cur.fetchall())[0]
        #render form
        tmpl = Template("""
            <html>
            <head><title>Edit Seller {{ sell.id }}</title></head>
            <body>
                <form action="." method="post">
                name: <input name="name" value="{% if sell.properties.name %}{{ sell.properties.name|escape }}{% endif %}"/><br/>
                {% if user.type == "admin" %}
                    boss: <input name="boss" value="{% if sell.boss %}{{ sell.boss|escape }}{% endif %}"/>
                    ({{ boss.properties.name }})<br/>
                {% else %}
                    <input type="hidden" name="boss" value="{{ sell.boss|escape }}"/>
                    boss: {{ sell.boss|escape }} ({{ boss.properties.name }})<br/>
                {% endif %}
                location: <input name="location" value="{% if sell.properties.location %}{{ sell.properties.location|escape }}{% endif %}"/><br/>
                login: <input name="login" value="{% if sell.login %}{{ sell.login|escape }}{% endif %}"/><br/>
                password: <input type="password" name="password" value="{% if sell.password %}{{ sell.password|escape }}{% endif %}"/><br/>
                created: {{ sell.properties.created|escape }}<br/>
                <input type="submit"/>
                {% if msg %}<br/>{{ msg|escape }}{% endif %}
                </form>
            </body>
            </html>
        """)
        html = str(tmpl.render(msg=data.get("msg"), sell=sell, boss=boss, user=user))
        return "200 OK", [('Content-type', 'text/html')], html
    #process form if POST method
    if req['REQUEST_METHOD'] == "POST":
        #parse post data
        data = dict(parse_qsl(req['wsgi.input'].read(int(req.get('CONTENT_LENGTH', '0')))))
        #validate form
        if not (data.get("name") and data.get("location") and data.get("login") and data.get("password") and data.get("boss")):
            return "302 Found", [('Location', '?msg=MissingFields')], ""
        #create json string for properties
        sell['properties']['name'] = data['name']
        sell['properties']['location'] = data['location']
        props = json.dumps(sell['properties'])
        #update field in db
        cur.execute("UPDATE solar.user SET boss=%s, login=%s, password=%s, properties=%s WHERE id=%s",
            (data['boss'], data['login'], data['password'], props, sell['id']))
        return "302 Found", [('Location', '/seller/{}/edit/?msg=Updated'.format(sell['id']))], ""

def seller_id_commission(req):
    return "200 OK", [('Content-type', 'text/html')], "<html><body>seller_id_commission</body></html>"

def seller_add(req):
    cur = req['cur']
    #require login
    user = helper_req2user(req)
    if not user:
        return "302 Found", [('Location', '/?next={}'.format(urllib.quote(req['PATH_INFO'])))], ""
    #validate permissions (admins, manufacturers (if distributor parameter), and distributors only)
    if not user['type'] in ["admin", "manufacturer", "distributor"]:
        return "302 Found", [('Location', '/?msg=InvalidPermission1')], ""
    #show form if GET method
    if req['REQUEST_METHOD'] == "GET":
        data = dict(parse_qsl(req['QUERY_STRING']))
        if data.get("boss") and user['type'] == "admin":
            cur.execute("SELECT * FROM solar.user WHERE `id` = %s", data['boss'])
            boss = helper_users(cur.fetchall())[0]
        else:
            boss = user
        #only allow manufacturers to add if they specify a distributor
        if user['type'] == "manufacturer" and not data.get("distributor"):
            return "302 Found", [('Location', '/?msg=NeedsDistributorParameter')], ""
        elif user['type'] == "manufacturer":
            cur.execute("SELECT * FROM solar.user WHERE `id` = %s", data['distributor'])
            boss = helper_users(cur.fetchall())[0]
            #bail out if distributor isn't under manufacturer
            if boss['boss'] != user['id']:
                return "302 Found", [('Location', '/?msg=InvalidPermission3')], ""
        #get boss dictionary
        tmpl = Template("""
            <html>
            <head><title>Add Seller</title></head>
            <body>
                <form action="." method="post">
                name: <input name="name" value="{% if data.name %}{{ data.name|escape }}{% endif %}"/><br/>
                {% if user.type == "admin" %}
                    boss: <input name="boss" value="{{ boss.id }}"/>
                    ({{ boss.properties.name }})<br/>
                {% else %}
                    <input type="hidden" name="boss" value="{{ boss.id|escape }}"/>
                    boss: {{ boss.id|escape }} ({{ boss.properties.name }})<br/>
                {% endif %}
                location: <input name="location" value="{% if data.location %}{{ data.location|escape }}{% endif %}"/><br/>
                login: <input name="login" value="{% if data.login %}{{ data.login|escape }}{% endif %}"/><br/>
                password: <input type="password" name="password" value="{% if data.password %}{{ data.password|escape }}{% endif %}"/><br/>
                <input type="submit"/>
                {% if data.msg %}<br/>{{ data.msg|escape }}{% endif %}
                </form>
            </body>
            </html>
        """)
        html = str(tmpl.render(data=data, user=user, boss=boss))
        return "200 OK", [('Content-type', 'text/html')], html
    #process form if POST method
    if req['REQUEST_METHOD'] == "POST":
        #parse post data
        data = dict(parse_qsl(req['wsgi.input'].read(int(req.get('CONTENT_LENGTH', '0')))))
        #validate form
        if not (data.get("name") and data.get("location") and data.get("login") and data.get("password") and data.get("boss")):
            return "302 Found", [('Location', '?msg=MissingFields')], ""
        #create json string for properties
        props = json.dumps({
            "name": data['name'],
            "location": data['location'],
            "created": date.today().strftime("%Y-%m-%d"),
            "picture": "none",
        })
        #insert field in db
        cur = req['cur']
        cur.execute("INSERT INTO solar.user (type, boss, login, password, properties) VALUES (%s, %s, %s, %s, %s)",
            ("seller", data['boss'], data['login'], data['password'], props))
        cur.execute("SELECT LAST_INSERT_ID()")
        results = cur.fetchall()
        dist_id = int(results[0][0])
        return "302 Found", [('Location', '/seller/{}/edit/'.format(dist_id))], ""

def order_id_edit(req):
    #require login
    user = helper_req2user(req)
    if not user:
        return "302 Found", [('Location', '/?next={}'.format(urllib.quote(req['PATH_INFO'])))], ""
    #get order to edit
    order_id = int(re.search("/order/([0-9]+)/edit/", req['PATH_INFO']).groups()[0])
    cur = req['cur']
    cur.execute("SELECT * FROM solar.order WHERE `id` = %s", order_id)
    results = helper_orders(cur.fetchall())
    if not results:
        return "302 Found", [('Location', '/?msg=MissingOrder')], ""
    order = results[0]
    #get order_product entries
    cur.execute("SELECT * FROM solar.order_product WHERE `order_id` = %s", order['id'])
    prod_m2m = helper_order_products(cur.fetchall())
    #validate permissions (admins, sellers and their bosses)
    if user['type'] != "admin":
        if user['type'] not in ["manufacturer", "distributor", "seller"]:
            return "302 Found", [('Location', '/?msg=InvalidPermission1')], ""
        if user['id'] != order['seller']:
            #user didn't match the seller, so maybe a boss?
            cur.execute("SELECT * FROM solar.user WHERE `id` = %s", order['seller'])
            seller = helper_users(cur.fetchall())[0]
            if not seller['boss']: #manufacturers don't have a boss
                return "302 Found", [('Location', '/?msg=InvalidPermission2')], ""
            if user['id'] != seller['boss']:
                #boss didn't match the seller, so maybe higher up?
                cur.execute("SELECT * FROM solar.user WHERE `id` = %s", seller['boss'])
                boss = helper_users(cur.fetchall())[0]
                if user['id'] != boss['boss']:
                    #doesn't match anyone in the food chain, so bail
                    return "302 Found", [('Location', '/?msg=InvalidPermission3')], ""
    #show form if GET method
    if req['REQUEST_METHOD'] == "GET":
        data = dict(parse_qsl(req['QUERY_STRING']))
        #get seller and buyer dictionaries
        cur.execute("SELECT * FROM solar.user WHERE `id` = %s", order['seller'])
        seller = helper_users(cur.fetchall())[0]
        cur.execute("SELECT * FROM solar.user WHERE `id` = %s", order['buyer'])
        buyer = helper_users(cur.fetchall())[0]
        #get list of product ids
        prod_ids = [i['product_id'] for i in prod_m2m]
        #set order status text
        if order['created']:
            order_status = "Created"
        if order['paid']:
            order_status = "Paid"
        if order['fulfilled']:
            order_status = "Delivered"
        if order['commissioned']:
            order_status = "Complete"
        #render form
        tmpl = Template("""
            <html>
            <head><title>Edit Order {{ order.id }}</title><style>input{width:4em;}span{display:inline-block;width:8em;}</style></head>
            <body>
                <h3>Order Status: {{ order_status }}</h3>
                <form action="." method="post">
                {% if user.type == "admin" %}
                    <span>seller:</span><input name="seller" value="{% if order.seller %}{{ order.seller|escape }}{% endif %}"/>
                    ({{ seller.properties.name }})<br/>
                {% else %}
                    <input type="hidden" name="seller" value="{{ order.seller|escape }}"/>
                    seller: {{ seller.properties.name|escape }}<br/>
                {% endif %}
                <span>buyer:</span><input name="buyer" value="{% if order.buyer %}{{ order.buyer|escape }}{% endif %}"/>
                ({{ buyer.properties.name }})<br/>
                <span>location:</span><input name="location" value="{% if order.properties.location %}{{ order.properties.location|escape }}{% endif %}"/><br/>
                <span>cost:</span><input name="cost" value="{% if order.cost %}{{ order.cost|escape }}{% endif %}"/><br/>
                <span>currency:</span><input name="currency" value="{% if order.currency %}{{ order.currency|escape }}{% endif %}"/><br/>
                <span>serial no.:</span><input name="product_ids" value="{{ prod_ids|join(',') }}"/><br/>
                {% if user.type == "admin" %}
                    <span>created:</span><input name="created" value="{% if order.created %}{{ order.created|escape }}{% endif %}"/><br/>
                    <span>paid:</span><input name="paid" value="{% if order.paid %}{{ order.paid|escape }}{% endif %}"/><br/>
                    <span>fulfilled:</span><input name="fulfilled" value="{% if order.fulfilled %}{{ order.fulfilled|escape }}{% endif %}"/><br/>
                    <span>commissioned:</span><input name="commissioned" value="{% if order.commissioned %}{{ order.commissioned|escape }}{% endif %}"/><br/>
                {% else %}
                    <input type="hidden" name="created" value="{% if order.created %}{{ order.created|escape }}{% endif %}"/>
                    created:<br/>{% if order.created %}{{ order.created|escape }}{% else %}Not Set{% endif %}<br/>
                    <input type="hidden" name="paid" value="{% if order.paid %}{{ order.paid|escape }}{% endif %}"/>
                    paid:<br/>{% if order.paid %}{{ order.paid|escape }}{% else %}Not Set{% endif %}<br/>
                    <input type="hidden" name="fulfilled" value="{% if order.fulfilled %}{{ order.fulfilled|escape }}{% endif %}"/>
                    fulfilled:<br/>{% if order.fulfilled %}{{ order.fulfilled|escape }}{% else %}Not Set{% endif %}<br/>
                    <input type="hidden" name="commissioned" value="{% if order.commissioned %}{{ order.commissioned|escape }}{% endif %}"/>
                    commissioned:<br/>{% if order.commissioned %}{{ order.commissioned|escape }}{% else %}Not Set{% endif %}<br/>
                {% endif %}
                <input type="submit"/><br/>
                {% if msg %}<br/>{{ msg|escape }}{% endif %}
                </form>
                <a href="/product/">Back to Inventory List</a>
            </body>
            </html>
        """)
        html = str(tmpl.render(msg=data.get("msg"), order=order, prod_ids=prod_ids, seller=seller, buyer=buyer, user=user, order_status=order_status))
        return "200 OK", [('Content-type', 'text/html')], html
    #process form if POST method
    if req['REQUEST_METHOD'] == "POST":
        #parse post data
        data = dict(parse_qsl(req['wsgi.input'].read(int(req.get('CONTENT_LENGTH', '0')))))
        #validate form
        if not (data.get("buyer") and data.get("seller") and data.get("location") and data.get("cost") and data.get("currency")):
            return "302 Found", [('Location', '?msg=MissingFields')], ""
        #get list of ids to change
        new_prod_ids = []
        if data.get("product_ids"):
            new_prod_ids = [int(i) for i in data['product_ids'].split(",")]
        #create json string for properties
        order['properties']['location'] = data['location']
        props = json.dumps(order['properties'])
        #update field in db
        cur.execute("UPDATE solar.order SET buyer=%s, seller=%s, cost=%s, currency=%s, created=%s, paid=%s, fulfilled=%s, commissioned=%s, properties=%s WHERE id=%s",
            (data['buyer'], data['seller'], data['cost'], data['currency'], data.get("created", None),
            data.get("paid", None), data.get("fulfilled", None), data.get("commissioned", None), props, order['id']))
        #delete current product ids associated with the order
        for m2m_id in [i['id'] for i in prod_m2m]:
            cur.execute("DELETE FROM solar.order_product WHERE id=%s", m2m_id)
        #insert new product ids associated with the order
        for prod_id in new_prod_ids:
            cur.execute("INSERT INTO solar.order_product (order_id, product_id) VALUES (%s, %s)", (order['id'], prod_id))
        return "302 Found", [('Location', '/order/{}/edit/?msg=Updated'.format(order['id']))], ""

def order_id_fulfill(req):
    return "200 OK", [('Content-type', 'text/html')], "<html><body>order_id_fulfill</body></html>"

def order_id_unfulfill(req):
    return "200 OK", [('Content-type', 'text/html')], "<html><body>order_id_unfulfill</body></html>"

def order_id_commission(req):
    return "200 OK", [('Content-type', 'text/html')], "<html><body>order_id_commission</body></html>"

def order_add(req):
    cur = req['cur']
    #require login
    user = helper_req2user(req)
    if not user:
        return "302 Found", [('Location', '/?next={}'.format(urllib.quote(req['PATH_INFO'])))], ""
    #validate permissions (admins, manufacturers, distributors, and sellers only)
    if not user['type'] in ["admin", "manufacturer", "distributor", "seller"]:
        return "302 Found", [('Location', '/?msg=InvalidPermission1')], ""
    #show form if GET method
    if req['REQUEST_METHOD'] == "GET":
        data = dict(parse_qsl(req['QUERY_STRING']))
        if data.get("seller") and user['type'] == "admin":
            cur.execute("SELECT * FROM solar.user WHERE `id` = %s", data['seller'])
            seller = helper_users(cur.fetchall())[0]
        else:
            seller = user
        #only allow distributers to add if they specify a seller under them
        if user['type'] == "distributor" and not data.get("seller"):
            return "302 Found", [('Location', '/?msg=NeedsSellerParameter')], ""
        elif user['type'] == "distributor":
            cur.execute("SELECT * FROM solar.user WHERE `id` = %s", data['seller'])
            seller = helper_users(cur.fetchall())[0]
            #bail out if seller isn't under distributor
            if seller['boss'] != user['id']:
                return "302 Found", [('Location', '/?msg=InvalidPermission3')], ""
        #only allow manufacturer to add if they specify a seller under them
        if user['type'] == "manufacturer" and not data.get("seller"):
            return "302 Found", [('Location', '/?msg=NeedsSellerParameter')], ""
        elif user['type'] == "manufacturer":
            cur.execute("SELECT * FROM solar.user WHERE `id` = %s", data['seller'])
            seller = helper_users(cur.fetchall())[0]
            cur.execute("SELECT * FROM solar.user WHERE `id` = %s", seller['boss'])
            dist = helper_users(cur.fetchall())[0]
            #bail out if seller isn't under manufacturer
            if dist['boss'] != user['id']:
                return "302 Found", [('Location', '/?msg=InvalidPermission3')], ""
        #see if the buyer can be resolved
        if data.get("buyer"):
            cur.execute("SELECT * FROM solar.user WHERE `id` = %s AND `type` = 'customer'", data['buyer'])
            results = helper_users(cur.fetchall())
            if results:
                data['buyer_name'] = results[0]['properties']['name']
                data['buyer_phone'] = results[0]['login']
        #render template
        tmpl = Template("""
            <html>
            <head><title>Add Order</title><style>input{width:4em;}span{display:inline-block;width:8em;}</style></head>
            <body>
                <h3>Order Form</h3>
                <form action="." method="post">
                {% if user.type == "admin" %}
                    <span>seller:</span><input name="seller" value="{{ seller.id }}"/>
                    ({{ seller.properties.name }})<br/>
                {% else %}
                    <input type="hidden" name="seller" value="{{ seller.id|escape }}"/>
                    seller: {{ seller.id|escape }} ({{ seller.properties.name }})<br/>
                {% endif %}
                <span>buyer name:</span><input name="buyer_name" value="{% if data.buyer_name %}{{ data.buyer_name|escape }}{% endif %}"/><br/>
                <span>buyer phone:</span><input name="buyer_phone" value="{% if data.buyer_phone %}{{ data.buyer_phone|escape }}{% endif %}"/><br/>
                <span>location:</span><input name="location" value="{% if data.location %}{{ data.location|escape }}{% endif %}"/><br/>
                <span>cost:</span><input name="cost" value="{% if data.cost %}{{ data.cost|escape }}{% endif %}"/><br/>
                <span>currency:</span><input name="currency" value="{% if data.currency %}{{ data.currency|escape }}{% else %}USD{% endif %}"/><br/>
                <span>serial no.:</span><input name="product_ids" value="{% if data.product_ids %}{{ data.product_ids|escape }}{% endif %}"/><br/>
                <input type="submit"/><br/>
                {% if data.msg %}<br/>{{ data.msg|escape }}{% endif %}
                {% if user.type == "seller" %}<a href="/order/add/">Add Another Order</a>{% endif %}
                </form>
            </body>
            </html>
        """)
        html = str(tmpl.render(data=data, user=user, seller=seller))
        return "200 OK", [('Content-type', 'text/html')], html
    #process form if POST method
    if req['REQUEST_METHOD'] == "POST":
        #parse post data
        data = dict(parse_qsl(req['wsgi.input'].read(int(req.get('CONTENT_LENGTH', '0')))))
        #validate form
        if not (data.get("seller") and data.get("buyer_name") and data.get("buyer_phone") and data.get("location") \
            and data.get("cost") and data.get("currency") and data.get("product_ids")):
            return "302 Found", [('Location', '?msg=MissingFields')], ""
        #split product ids into list
        new_prod_ids = []
        if data.get("product_ids"):
            new_prod_ids = [int(i) for i in data['product_ids'].split(",")]
        #make sure those product ids exist and aren't part of another order
        for prod_id in new_prod_ids:
            cur.execute("SELECT * FROM solar.product WHERE `id` = %s", prod_id)
            if not cur.fetchall():
                return "302 Found", [('Location', '?msg=BadProductSerial')], ""
            cur.execute("SELECT * FROM solar.order_product WHERE `product_id` = %s", prod_id)
            if cur.fetchall():
                return "302 Found", [('Location', '?msg=ProductSerialUsedInAnotherOrder')], ""
        #see if that phone number already exists
        cur.execute("SELECT * FROM solar.user WHERE `login` = %s", data['buyer_phone'])
        results = helper_users(cur.fetchall())
        if results:
            cust_id = results[0]['id']
            #update location for customer
            cust_props = json.dumps({
                "name": results[0]['properties']['name'],
                "location": data['location'],
                "created": results[0]['properties']['created'],
                "picture": results[0]['properties']['picture'],
            })
            cur.execute("UPDATE solar.user SET properties=%s WHERE id=%s", (cust_props, cust_id))
        #no phone number, so create a new customer
        else:
            cust_props = json.dumps({
                "name": data['buyer_name'],
                "location": data['location'],
                "created": date.today().strftime("%Y-%m-%d"),
                "picture": "none",
            })
            cur.execute("INSERT INTO solar.user (type, boss, login, password, properties) VALUES (%s, %s, %s, %s, %s)",
                ("customer", data['seller'], data['buyer_phone'], "x", cust_props))
            cur.execute("SELECT LAST_INSERT_ID()")
            results = cur.fetchall()
            cust_id = int(results[0][0])
        #create json string for properties and created timestamp
        props = json.dumps({"location": data['location']})
        created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fulfilled = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        #insert field in db
        print data['cost'], data['currency'], created, None, None, None, data['seller'], cust_id, props
        cur.execute("INSERT INTO solar.order (cost, currency, created, paid, fulfilled, commissioned, seller, buyer, properties) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (data['cost'], data['currency'], created, None, fulfilled, None, data['seller'], cust_id, props))
        cur.execute("SELECT LAST_INSERT_ID()")
        results = cur.fetchall()
        order_id = int(results[0][0])
        #insert new product ids associated with the order and update the product owner
        for prod_id in new_prod_ids:
            cur.execute("UPDATE solar.product SET current_owner=%s WHERE id=%s", (cust_id, prod_id))
            cur.execute("INSERT INTO solar.order_product (order_id, product_id) VALUES (%s, %s)", (order_id, prod_id))
        #send sms
        from twilio.rest import TwilioRestClient
        account_sid = "ACc41fd848125b312e7e6467482a8b9759"
        auth_token = "557c125f2ed22b236bc3fb495e76026e"
        client = TwilioRestClient(account_sid, auth_token)
        message = client.sms.messages.create(body="$5 Order Confirmation, Reply 'OK'",
            to="+15127691164", from_="+15128616105")
        print message.sid
        return "302 Found", [('Location', '/order/{}/edit/'.format(order_id))], ""

def pay(req):
    return "200 OK", [('Content-type', 'text/html')], "<html><body>pay</body></html>"

def recreate(req):
    #CREATE DATABASE solar;
    #CREATE USER 'solaruser'@'localhost' IDENTIFIED BY 'solarpassword';
    #GRANT ALL PRIVILEGES ON `solar` . * TO 'solaruser'@'localhost';
    cur = req['cur']

    recreate_steps = [
        "DROP TABLE IF EXISTS `order`",
        "DROP TABLE IF EXISTS `order_product`",
        "DROP TABLE IF EXISTS `payment`",
        "DROP TABLE IF EXISTS `product`",
        "DROP TABLE IF EXISTS `session`",
        "DROP TABLE IF EXISTS `user`",
        """
        CREATE TABLE IF NOT EXISTS `order` (
         `id` int(11) NOT NULL AUTO_INCREMENT,
         `cost` float NOT NULL,
         `currency` varchar(5) NOT NULL,
         `created` datetime NOT NULL,
         `paid` datetime ,
         `fulfilled` datetime,
         `commissioned` datetime ,
         `seller` int(11) NOT NULL,
         `buyer` int(11) NOT NULL,
         `properties` text NOT NULL,
         PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=latin1
        """,
        """
        CREATE TABLE IF NOT EXISTS `order_product` (
         `id` int(11) NOT NULL AUTO_INCREMENT,
         `order_id` int(11) NOT NULL,
         `product_id` int(11) NOT NULL,
         PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=latin1
        """,
        """
        CREATE TABLE IF NOT EXISTS `payment` (
         `id` int(11) NOT NULL AUTO_INCREMENT,
         `user_id` int(11) NOT NULL,
         `amount` float NOT NULL,
         `currency` varchar(5) NOT NULL,
         `created` datetime NOT NULL,
         `order_id` int(11),
         PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=latin1
        """,
        """
        CREATE TABLE IF NOT EXISTS `product` (
         `id` int(11) NOT NULL AUTO_INCREMENT,
         `created_by` int(11) NOT NULL,
         `current_owner` int(11) NOT NULL,
         `properties` text NOT NULL,
         PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=latin1
        """,
        """
        CREATE TABLE IF NOT EXISTS `session` (
         `id` varchar(100) NOT NULL,
         `user` int(11) NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=latin1
        """,
        """
        CREATE TABLE IF NOT EXISTS `user` (
         `id` int(11) NOT NULL AUTO_INCREMENT,
         `type` varchar(20) NOT NULL,
         `boss` int(11) NOT NULL,
         `login` varchar(100) NOT NULL,
         `password` varchar(100) NOT NULL,
         `properties` text NOT NULL,
         PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=latin1
        """,
        """
        INSERT INTO solar.user (type, boss, login, password, properties) VALUES ('admin', 0, 'a', 'p', '{"name": "admininstrator", "created": "2013-09-14", "location": "Oakland", "picture": "none"}'),
                                                                          ('manufacturer', 0, 's', 'p', '{"name": "manufacturer1", "created": "2006-01-01", "location": "Beijing", "picture": "none"}'),
                                                                          ('distributor', 2, 'j', 'p', '{"name": "DistributorJane", "created": "2012-05-01", "location": "Tanzania", "picture": "none"}'),
                                                                          ('seller', 3, 'e', 'p', '{"name": "SellerEduardo", "created": "2012-05-01", "location": "Tanzania", "picture": "none"}')
        """,
        """
        INSERT INTO solar.product (created_by, current_owner, properties) VALUES (2, 3, '{"name": "lamp", "created": "2013-09-14"}'),
                                                                           (2, 3, '{"name": "lamp", "created": "2013-09-14"}'),
                                                                           (2, 3, '{"name": "lamp", "created": "2013-09-14"}'),
                                                                           (2, 3, '{"name": "lamp", "created": "2013-09-14"}'),
                                                                           (2, 3, '{"name": "lamp", "created": "2013-09-14"}'),
                                                                           (2, 3, '{"name": "lamp", "created": "2013-09-14"}')
        """,
        #"""
        #INSERT INTO solar.order (cost ,currency ,created ,paid,fulfilled,commissioned,seller,buyer,properties)
        #VALUES ('50.00', 'USD','2013-09-14 00:00:00', NULL , NULL , NULL ,  6,  10,  '{"location": "Kenya"}'),
        #       ('50.00', 'USD','2013-09-14 00:00:00', NULL , NULL , NULL ,  7,  11,  '{"location": "Kenya"}'),
        #       ('50.00', 'USD','2013-09-14 00:00:00', NULL , NULL , NULL ,  8,  12,  '{"location": "Uganda"}'),
        #       ('50.00', 'USD','2013-09-14 00:00:00', NULL , NULL , NULL ,  8,  13,  '{"location": "Uganda"}'),
        #       ('50.00', 'USD','2013-09-14 00:00:00', NULL , NULL , NULL ,  9,  14,  '{"location": "Uganda"}'),
        #       ('50.00', 'USD','2013-09-14 00:00:00', NULL , NULL , NULL ,  9,  15,  '{"location": "Kenya"}')
        #""",
        #"""
        #INSERT INTO solar.order_product (order_id, product_id)
        #VALUES (1, 1),
        #       (2, 2),
        #       (3, 4),
        #       (4, 5),
        #       (5, 6),
        #       (6, 7)
        #""",
        #"""
        #INSERT INTO solar.payment (user_id, amount, currency, created, order_id)
        #VALUES (10, 50.00, 'USD', '2013-09-14', 1),
        #       (11, 50.00, 'USD', '2013-09-14', 2)
        #""",
    ]

    for step in recreate_steps:
        cur.execute(step)

    return "200 OK", [('Content-type', 'text/html')], "<html><body>Database Reset</body></html>"

