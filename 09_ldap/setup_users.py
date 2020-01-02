import os
import csv
from json import load
from subprocess import run
from unidecode import unidecode
from common import create_ldif, add_ldif, mkdir_p


def get_new_users():
    with open('srcs/students.csv', 'r') as new_users_file:
        reader = csv.DictReader(new_users_file)
        return [user for user in reader]


def new_user_attributes(last_name):
    def get_list_user_attributes(attribute):
        # Source (adapted): https://serverfault.com/questions/725766/how-to-list-uid-of-all-the-users-of-ldap/946701#946701
        cmd = "ldapsearch -H ldapi:/// -x -LLL uid=* | grep {}: | cut -d' ' -f2"
        p = run(cmd.format(attribute), shell=True, capture_output=True)
        return p.stdout.decode('utf-8').split('\n')[:-1]
    # Replace any non-ascii chars and lowercase it
    last_name = unidecode(last_name.lower())
    # Get a new username
    # (first 8 letters of last_name + 1/2/3/4/... if needed for uniqueness)
    usernames = get_list_user_attributes('uid') + ['root']
    username = last_name[:8]
    if username in usernames:
        i = 1
        while last_name[:8] + str(i) in usernames:
            i += 1
        username = last_name[:8] + str(i)
    new_user = {'username': username}
    # Get a new user uid (smallest free number over 2000)
    uids = list(map(int, get_list_user_attributes('uidNumber')))
    uid = 2000
    while uid in uids:
        uid += 1
    new_user['uid'] = uid
    # Set fixed gid and add home directory
    new_user['gid'] = 2000
    new_user['home_dir'] = '/home/' + username
    return new_user


def add_user_certificate(username, full_name):
    # Generate passphrase and write it to file
    mkdir_p('certs')
    run("diceware -n 6 > certs/{}.passphrase".format(username), shell=True)
    # Generate user RSA key
    cmd = "openssl genrsa -aes256 -passout file:certs/{0}.passphrase -out certs/{0}.key 4096"
    run(cmd.format(username), shell=True)
    # Generate certificate config and write it to file
    create_ldif('cnf', {'username': username, 'name': full_name},
                'tmpdir/certs/{}.cnf'.format(username))
    # Generate certificate signing request
    cmd = "openssl req -new -key certs/{0}.key -passin file:certs/{0}.passphrase -config tmpdir/certs/{0}.cnf -out tmpdir/certs/{0}.csr"
    run(cmd.format(username), shell=True)
    # Sign certificate using CA
    cmd = "openssl x509 -req -days 3650 -in tmpdir/certs/{0}.csr -passin file:/etc/ldap/ssl/team10-ca.passphrase -CA /etc/ldap/ssl/team10-ca.cert.pem -CAkey /etc/ldap/ssl/team10-ca.key.pem -CAserial /etc/ldap/ssl/team10-ca.cert.srl -out certs/{0}.crt"
    run(cmd.format(username), shell=True)
    # Convert certificate to LDAP usable format
    cmd = "openssl x509 -inform pem -outform der -in certs/{0}.crt -out tmpdir/certs/{0}.crt.der"
    run(cmd.format(username), shell=True)
    # Generate ldif for change and execute it
    filename = 'tmpdir/certs/{}.ldif'.format(username)
    create_ldif('add_certificate_ldif',
                {'username': username, 'pwd': os.getcwd()},
                filename)
    add_ldif(filename)


def add_new_user(user, add_certificate=False):
    # Prepare some information bits for later
    new_user = new_user_attributes(user['Name'])

    # Fill template with user information
    user_info = {
        'username': new_user['username'],
        'matr_nr': user['Matrikelnummer'],
        'first_name': user['Vorname'],
        'last_name': user['Name'],
        'phone': user['Telefon'],
        'gender': 'male' if user['Geschlecht'] == 'm' else 'female',
        'dob': user['Geburtsdatum'],
        'pob': user['Geburtsort'],
        'nationality': user['Nationalität'],
        'address': user['Straße'],
        'postal_code': user['PLZ'],
        'city': user['Ort'],
        'uid': new_user['uid'],
        'gid': new_user['gid'],
        'home_dir': new_user['home_dir']
    }
    filename = 'tmpdir/users/{}.ldif'.format(new_user['username'])
    create_ldif('student', user_info, filename)

    # Add ldif to server
    print("Creating user {}:".format(new_user['username']))
    add_ldif(filename)
    # Specific user deletion: ldapdelete -w team10 -H ldapi:/// -D "cn=admin,dc=team10,dc=psa,dc=in,dc=tum,dc=de" "uid=mustermann,ou=Students,dc=team10,dc=psa,dc=in,dc=tum,dc=de"
    # Or complete organizational unit: ldapdelete -w team10 -H ldapi:/// -D "cn=admin,dc=team10,dc=psa,dc=in,dc=tum,dc=de" -x -r "ou=Students,dc=team10,dc=psa,dc=in,dc=tum,dc=de"

    # Create user certificate and add it to LDAP
    if add_certificate:
        full_name = user_info['first_name'] + ' ' + user_info['last_name']
        add_user_certificate(new_user['username'], full_name)


def add_new_users():
    add_certificates = input("Generate user certificates? y/N ") == 'y'
    for user in get_new_users():
        add_new_user(user, add_certificates)


def get_existing_users():
    with open('srcs/existing_users.json', 'r') as f:
        return load(f)


def add_existing_user(user):
    user['gid'] = 10025
    user['home_dir'] = '/home/' + user['username']
    filename = 'tmpdir/users/{}.ldif'.format(user['username'])
    create_ldif('existing_user', user, filename)
    print("Creating user {}:".format(user['username']))
    add_ldif(filename)


def add_existing_users():
    for user in get_existing_users():
        add_existing_user(user)
