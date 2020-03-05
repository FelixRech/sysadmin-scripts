import sys
from subprocess import run
from datetime import datetime

print(f"Intrusion detection called on {datetime.now().isoformat()}")
sys.stdout.flush()

# rkhunter
rkhunter = "http_proxy=\"proxy.in.tum.de:8080\" rkhunter --update --cronjob --report-warnings-only --nocolors --skip-keypress"
out = run(rkhunter, shell=True, capture_output=True).stdout.decode('utf-8')

if out != "":
    print("rkhunter found violations, sending e-mail")
    cmd = (f"{rkhunter} | swaks "
           "--to \"rech@psa-team10.in.tum.de\" --from \"rkhunter@psa-team10.in.tum.de\" "
           "-tls --server mail.psa-team10.in.tum.de "
           "--header \"Subject: [rkhunter] Warnings found for $(hostname)\" "
           "--body - ")
    run(cmd, shell=True)
else:
    print("rkhunter found no warnings")

# Tripwire
out = run("/usr/sbin/tripwire -m c -s", shell=True,
          capture_output=True).stdout.decode('utf-8')

if not "Total violations found:  0" in out:
    print("Tripwire found violations, sending e-mail")
    cmd = ("/usr/sbin/tripwire -m c -s | swaks "
           "--to \"rech@psa-team10.in.tum.de\" --from \"tripwire@psa-team10.in.tum.de\" "
           "-tls --server mail.psa-team10.in.tum.de "
           "--header \"Subject: [Tripwire] Violations found for $(hostname)\" "
           "--body - ")
    run(cmd, shell=True)
else:
    print("Tripwire found no violations")
