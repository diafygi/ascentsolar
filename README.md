ascentsolar
===========

Fixing last mile distribution in developing world solar products

1. create a mysql database "solar"
2. mysql> CREATE DATABASE solar;
3. mysql> CREATE USER 'solaruser'@'localhost' IDENTIFIED BY 'solarpassword';
4. mysql> GRANT ALL PRIVILEGES ON `solar` . * TO 'solaruser'@'localhost';
5. run "python server.py" in command line
6. open browser and go to http://localhost:8888/
7. go to http://localhost:8888/reset/ to reset database
8. go to http://localhost:8888/product/ and login as "j" and "p" for password
9. /product/ shows typical inventory
