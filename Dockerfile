FROM fedora:rawhide

COPY build.py requirements.txt build /build/
WORKDIR /build
RUN dnf --setopt=install_weak_deps=false -y install createrepo rpm-build rpm-sign yum-utils python3.12 pip3 && dnf clean all
RUN pip3 install -r /build/requirements.txt

ENTRYPOINT python3 build.py
