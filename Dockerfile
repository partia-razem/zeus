#####
# zeus_dev (for mounting the source code)
#####

FROM ubuntu:20.04 AS zeus_dev

ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get -y update && apt-get -yy install \
    build-essential \
    python3.8 \
    python3.8-dev \
    python3-venv \
    libgmp-dev \
    libmpfr-dev \
    libmpc-dev \
    postgresql-client-12 \
    moreutils \
    gettext

RUN useradd --create-home --shell /bin/bash user

USER user
WORKDIR /home/user

# Create and activate virtualenv
ENV VIRTUAL_ENV=/home/user/env
RUN python3.8 -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN mkdir zeus
WORKDIR /home/user/zeus

# Install Python packages
COPY --chown=user:user requirements.txt .
RUN pip install -r requirements.txt

EXPOSE 8000

#####
# zeus_prod (source code copied, files built)
#####

FROM zeus_dev AS zeus_prod

# Copy the rest of Zeus sources
COPY --chown=user:user . .

# Use 'settings.prod' as default Django settings, docker-compose-prod.yml will
# override it
ENV DJANGO_SETTINGS_MODULE=settings.prod

# Compile translations
RUN ./compile-translations.sh

# Collect static files
RUN python manage.py collectstatic --noinput

EXPOSE 8000
