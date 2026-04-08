FROM odoo:17.0

USER root

COPY ./addons-custom/requirements.txt /requirements.txt

RUN pip3 install -r /requirements.txt

USER odoo