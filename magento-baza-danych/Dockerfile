FROM mysql:5.7.22
ADD magento.sql /docker-entrypoint-initdb.d
CMD ["mysqld", "--character-set-server=utf8", "--collation-server=utf8_general_ci"]