"""Advisory password guidance; existing OTP and owner guards stay authoritative."""


def password_help(client, email):
    result = client.call('POST', '/rest/v1/rpc/member_password_creation_guard_v1',
                         {'p_email': email.strip().lower()})
    if not isinstance(result, dict):
        return {'action': None}
    member = result.get('is_member') is True
    exists = result.get('has_existing_auth_user') is True
    status = result.get('password_status')
    action = None
    if member and exists and status == 'password_exists':
        action = 'reset'
    elif member and exists and status == 'password_not_set':
        action = 'create_verified'
    elif member and not exists and status == 'auth_user_missing' and result.get('allow_create_password') is True:
        action = 'create'
    elif result.get('is_member') is False and status == 'member_not_found':
        action = 'verify'
    return {'action': action}
