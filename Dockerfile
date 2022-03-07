FROM python:3.6.4
RUN mkdir -p /usr/src/app
COPY . /usr/src/app
RUN pip install -r /usr/src/app/requirements.txt \
    && python /usr/src/app/main.py init
CMD python /usr/src/app/main.py run