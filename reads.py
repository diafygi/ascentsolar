from jinja2 import Template
from jinja2 import Environment
import jinja2
import json
import writes
import urllib
env = jinja2.Environment(loader=jinja2.FileSystemLoader("read_templates")) 

def manufacturer(req):
	db = req['cur'];
	user = writes.helper_req2user(req);
	if(user is not None):
		if(user['type'] == 'admin'):
			tmpl = env.get_template( "manufacturer.html")
			manufacturers = get_users(db, 'manufacturer')
			countries = []

			for manufacturer in manufacturers:
				if manufacturer['location'] not in countries:
					countries.append(manufacturer['location'])
				 
			html = tmpl.render(
			    manufacturers = get_users(db, 'manufacturer'),
			    distributors = get_users(db, 'distributor'),
			    sellers = get_users(db, 'seller'),
				countries = countries
			)
			return "200 OK", [('Content-type', 'text/html')], str(html)
		else:
			return "200 OK", [('Content-type', 'text/html')], 'Not an admin!'
	else:
		return "200 OK", [('Content-type', 'text/html')], 'Please login'

def manufacturer_id(req):
	id = req['PATH_INFO'].split("/")[2];
	db = req['cur'];
	manufacturer = get_users(db, 'manufacturer', id)[0]
	tmpl = env.get_template( "manufacturer_id.html")
		 
	html = tmpl.render(
	    manufacturer = manufacturer,
		distributors = get_employees(db, 'manufacturer', manufacturer['id'])
	)
	return "200 OK", [('Content-type', 'text/html')], str(html)

def distributor(req):
	db = req['cur'];
	user = writes.helper_req2user(req);
	if(user is not None):
		if(user['type'] == 'manufacturer' or user['type'] == 'admin'):
			tmpl = env.get_template( "distributor.html")
			distributors = None
			if(user['type'] == 'manufacturer'):
				distributors = get_employees(db, 'manufacturer', user['id'])
			else:
				distributors = get_users(db, 'distributor')

			countries = []
			for distributor in distributors:
				if distributor['location'] not in countries:
					countries.append(distributor['location'])


			html = tmpl.render(
			    distributors = distributors,
			    sellers = get_users(db, 'seller'),
				countries = countries
			)
			return "200 OK", [('Content-type', 'text/html')], str(html)
		else:
			return "200 OK", [('Content-type', 'text/html')], 'Not a manufacturer!'
	else:
		return "200 OK", [('Content-type', 'text/html')], 'Please login'

def distributor_id(req):
	id = req['PATH_INFO'].split("/")[2];
	db = req['cur'];
	user = writes.helper_req2user(req);
	distributor = None
	if(user['type'] == 'manufacturer'):
		distributors = get_employees(db, 'manufacturer', user['id'])
		for dist in distributors:
			if dist['boss'] == user['id']:
				distributor = get_users(db, 'distributor', id)[0]
		if(distributor is None):
			return "200 OK", [('Content-type', 'text/html')], 'Not your employee!'
	elif(user['type'] == 'admin'):
		distributor = get_users(db, 'distributor', id)[0]
	elif(user['type'] == 'distributor'):
			distributor = get_users(db, 'distributor', id)[0]
	else:
		return "200 OK", [('Content-type', 'text/html')], 'Not enough priviledges'
	tmpl = env.get_template( "distributor_id.html")
		 
	html = tmpl.render(
	    distributor = distributor,
		sellers = get_employees(db, 'distributor', distributor['id'])
	)
	return "200 OK", [('Content-type', 'text/html')], str(html)

def seller(req):
	db = req['cur'];
	user = writes.helper_req2user(req);
	if(user is not None):
		tmpl = env.get_template( "seller.html")
		distributors = None
		sellers = []
		if(user['type'] == 'manufacturer'):
			distributors = get_employees(db, 'manufacturer', user['id'])
			for distributor in distributors:
				seller = get_employees(db, 'distributor', distributor['id'])
				for s in seller:
					sellers.append(s)
			if(sellers is None):
				return "200 OK", [('Content-type', 'text/html')], 'No sellers'
		elif(user['type'] == 'distributor'):
			distributors = get_employees(db, 'distributor', user['id'])
		elif(user['type'] == 'admin'):
			sellers = get_users(db, 'seller')
		else:
			return "200 OK", [('Content-type', 'text/html')], 'Not enough priviledges'

		countries = []
		for seller in sellers:
			if seller['location'] not in countries:
				countries.append(seller['location'])


		html = tmpl.render(
		    sellers = sellers,
		    customers = get_users(db, 'customer'),
			countries = countries
		)
		return "200 OK", [('Content-type', 'text/html')], str(html)
	else:
		return "200 OK", [('Content-type', 'text/html')], 'Please login'

def seller_id(req):
	id = req['PATH_INFO'].split("/")[2];
	db = req['cur'];
	seller = get_users(db, 'seller', id)[0]
	tmpl = env.get_template( "seller_id.html")
		 
	html = tmpl.render(
	    seller = seller,
		customers = get_employees(db, 'seller', seller['id'])
	)
	return "200 OK", [('Content-type', 'text/html')], str(html)

def customer(req):
	db = req['cur'];
	user = writes.helper_req2user(req);
	tmpl = env.get_template( "customer.html")
		 
	html = tmpl.render(
	    customers = get_users(db, 'customer')
	)
	return "200 OK", [('Content-type', 'text/html')], str(html)

def customer_id(req):
	id = req['PATH_INFO'].split("/")[2];
	db = req['cur'];
	customer = get_users(db, 'customer', id)[0]
	tmpl = env.get_template( "customer_id.html")
		 
	html = tmpl.render(
	    customer = customer
	    )
	return "200 OK", [('Content-type', 'text/html')], str(html)

def product(req):
	#require login
	user = writes.helper_req2user(req);
	if not user:
	    return "302 Found", [('Location', '/?next={}'.format(urllib.quote(req['PATH_INFO'])))], ""
	db = req['cur'];
	user = writes.helper_req2user(req);
	products = []
	distributors = None
	sellers = []
	customers = []
	if(user['type'] == 'manufacturer'):
		distributors = get_employees(db, 'manufacturer', user['id'])
		for distributor in distributors:
			seller = get_employees(db, 'distributor', distributor['id'])
			for s in seller:
				sellers.append(s)
		if(sellers is None):
			return "200 OK", [('Content-type', 'text/html')], 'No sellers'
		else:
			for seller in sellers:
				customer = get_employees(db, 'seller', seller['id'])
				for c in customer:
					customers.append(c)
	elif(user['type'] == 'distributor'):
		sellers = get_employees(db, 'distributor', user['id'])
		for seller in sellers:
			customer = get_employees(db, 'seller', seller['id'])
			for c in customer:
				customers.append(c)
	elif(user['type'] == 'seller'):
		customer = get_employees(db, 'seller', user['id'])
		for c in customer:
			customers.append(c)
	else:
		return "200 OK", [('Content-type', 'text/html')], 'Not enough priviledges'

	for p in get_products(db, user['id']):
		products.append(p)

	if(distributors is not None and distributors ):
		for d in distributors:
			for p in get_products(db, d['id']):
				products.append(p)
	if(sellers is not None and sellers ):
		for s in sellers:
			for p in get_products(db, s['id']):
				products.append(p)
	if(customers is not None and customers ):
		for c in customers:
			for p in get_products(db, c['id']):
				products.append(p)

	products = sorted(products, key=lambda k: k['id'])

	tmpl = env.get_template( "product.html")
	html = tmpl.render(
	    products = products,
	    user = user
	    )
	return "200 OK", [('Content-type', 'text/html')], str(html)

def product_id(req):
	id = req['PATH_INFO'].split("/")[2];
	db = req['cur'];
	product = get_product(db, id)[0]
	tmpl = env.get_template( "product_id.html")
	html = tmpl.render(
	    product = product
	    )
	return "200 OK", [('Content-type', 'text/html')], str(html)

def seller_uncommisioned(req):
	return "200 OK", [('Content-type', 'text/html')], "<html><body>seller_uncommisioned</body></html>"

def order(req):
	return "200 OK", [('Content-type', 'text/html')], "<html><body>orders</body></html>"

def order_id(req):
	id = req['PATH_INFO'].split("/")[2];
	return "200 OK", [('Content-type', 'text/html')], "<html><body>order properties</body></html>"

def order_unpaid(req):
	return "200 OK", [('Content-type', 'text/html')], "<html><body>unpaid order_unpaid</body></html>"

def order_uncommisioned(req):
	return "200 OK", [('Content-type', 'text/html')], "<html><body>order_uncommisioned</body></html>"

def order_unfulfilled(req):
	return "200 OK", [('Content-type', 'text/html')], "<html><body>order_unfulfilled</body></html>"


#helpers
def get_users(db, type= 'none', id= -1):
	users = []

	query = "SELECT id, boss, login, type, properties from user "
	if(id != -1 and type != 'none'):
		query += " where type like '"+type+"' and id = "+str(id)
	elif(id != -1):
		query += " where id = "+str(id)
	elif(type != 'none'):
		query += " where type like '"+type+"'"

	db.execute(query)
	rows = db.fetchall()

	for row in rows:
		pr = {'name': 'name', 'created': 'created', 'location': 'location', 'picture': 'picture'}
		try:
			pr = json.loads(row[4])
		except:
			pass
		users.append({'id': row[0], 'boss': row[1], 'login': row[2], 'type': row[3], 'name': pr['name'], 'created': pr['created'], 'location': pr['location'], 'picture': pr['picture']})

	return users

def get_product(db, id= -1):
	products = []

	query = "SELECT id, created_by, current_owner, properties from product "

	db.execute(query)
	rows = db.fetchall()

	for row in rows:
		pr = {'name': 'name', 'created': 'created'}
		try:
			pr = json.loads(row[3])
		except:
			pass
		creator = get_users(db, 'none', row[1])[0]
		owner = get_users(db, 'none', row[2])[0]
		order_id = -1

		query = "SELECT order_id from order_product where product_id = "+str(row[0])
		db.execute(query)
		orderrows = db.fetchall()
		for orderrow in orderrows:
			order_id = orderrow[0]

		products.append({'id': row[0], 'created_by': creator, 'current_owner': owner, 'name': pr['name'], 'created': pr['created'], 'order_id': order_id})
	return products

def get_products(db, user_id):
	products = []

	query = "SELECT id, created_by, current_owner, properties from product where  current_owner = "+str(user_id)

	db.execute(query)
	rows = db.fetchall()
	print(query)
	for row in rows:
		pr = {'name': 'name', 'created': 'created'}
		try:
			pr = json.loads(row[3])
		except:
			pass

		creator = get_users(db, 'none', row[1])[0]
		owner = get_users(db, 'none', row[2])[0]

		products.append({'id': row[0], 'created_by': creator, 'current_owner': owner, 'name': pr['name'], 'created': pr['created']})
	return products


def get_employees(db, boss_type, boss_id):
	users = []

	employee_type = ''
	if(boss_type == 'manufacturer'):
		employee_type = 'distributor'
	elif(boss_type == 'distributor'):
		employee_type = 'seller'
	elif(boss_type == 'seller'):
		employee_type = 'customer'

	query = "SELECT id from user where type like '"+str(employee_type)+"' and boss = "+str(boss_id)
	print(query)
	db.execute(query)
	rows = db.fetchall()

	for row in rows:
		users.append(get_users(db, employee_type, row[0])[0])

	return users
