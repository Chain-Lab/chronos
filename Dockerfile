FROM python:3.6.4
RUN mkdir -p /usr/src/app
COPY . /usr/src/app
RUN pip install -r /usr/src/app/requirements.txt \
    && cd /usr/src/app \
    && chmod +x startup.sh \
    && rm ./conf/config.ini
ENTRYPOINT ["/usr/src/app/startup.sh"]