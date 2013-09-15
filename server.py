import reads
import writes
import re
import MySQLdb

#Run in the command line: "python server.py"
#Open browser and go to http://localhost:8888/
#Go to http://localhost:8888/recreate/ to reset database to example

def URLS():
    yield ("^/$", writes.login)
    yield ("^/logout/$", writes.logout)
    yield ("^/manufacturer/$", reads.manufacturer)
    yield ("^/manufacturer/[0-9]+/$", reads.manufacturer_id)
    yield ("^/manufacturer/[0-9]+/edit/$", writes.manufacturer_id_edit)
    yield ("^/manufacturer/add/$", writes.manufacturer_add)

    yield ("^/product/$", reads.product)
    yield ("^/product/[0-9]+/$", reads.product_id)
    yield ("^/product/[0-9]+/edit/$", writes.product_id_edit)
    yield ("^/product/add/$", writes.product_add)
    yield ("^/product/mass-assign/$", writes.product_mass_assign)

    yield ("^/distributor/$", reads.distributor)
    yield ("^/distributor/[0-9]+/$", reads.distributor_id)
    yield ("^/distributor/[0-9]+/edit/$", writes.distributor_id_edit)
    yield ("^/distributor/add/$", writes.distributor_add)

    yield ("^/seller/$", reads.seller)
    yield ("^/seller/[0-9]+/$", reads.seller_id)
    yield ("^/seller/[0-9]+/edit/$", writes.seller_id_edit)
    yield ("^/seller/[0-9]+/commission/$", writes.seller_id_commission)
    yield ("^/seller/add/$", writes.seller_add)

    yield ("^/order/$", reads.order)
    yield ("^/order/[0-9]+/$", reads.order_id)
    yield ("^/order/[0-9]+/edit/$", writes.order_id_edit)
    yield ("^/order/[0-9]+/fulfill/$", writes.order_id_fulfill)
    yield ("^/order/[0-9]+/unfulfill/$", writes.order_id_unfulfill)
    yield ("^/order/[0-9]+/commission/$", writes.order_id_commission)
    yield ("^/order/add/$", writes.order_add)
    yield ("^/pay/$", writes.pay)

    yield ("^/customer/$", reads.customer)
    yield ("^/customer/[0-9]+/$", reads.customer_id)

    yield ("^/recreate/$", writes.recreate)
    yield ("^/reset/$", writes.recreate)
    yield ("^/reload/$", writes.recreate)

def app(req, resp):
    for url, page in URLS():
        if re.match(url, req['PATH_INFO']):
            req['db'] = MySQLdb.connect(host="localhost", user="solaruser", passwd="solarpassword", db="solar")
            req['cur'] = req['db'].cursor()
            status, headers, data = page(req)
            resp(status, headers)
            req['cur'].close()
            req['db'].commit()
            req['db'].close()
            return [data]
    resp('404 Not Found', [('Content-type', 'text/plain')])
    return ["404 Not Found"]

from wsgiref.simple_server import make_server
make_server('', 8888, app).serve_forever()
