# Day 4 test fixture - NOT part of the harness itself.
# A minimal SSH server used only to give SSHExecutor a real target to prove
# itself against. Alpine + OpenSSH + coreutils/findutils/grep (so the same
# find/grep-based list_files and grep tools work here exactly as they do
# locally), key-only auth, no password login.
FROM alpine:3.19
RUN apk add --no-cache openssh coreutils findutils grep bash \
    && ssh-keygen -A \
    && adduser -D ody \
    && mkdir -p /home/ody/.ssh /work \
    && chown ody:ody /home/ody/.ssh /work \
    && chmod 700 /home/ody/.ssh \
    && sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config \
    && sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin no/' /etc/ssh/sshd_config
COPY authorized_keys /home/ody/.ssh/authorized_keys
RUN chown ody:ody /home/ody/.ssh/authorized_keys && chmod 600 /home/ody/.ssh/authorized_keys
EXPOSE 22
CMD ["/usr/sbin/sshd", "-D", "-e"]
