import oauth2
from config import github_oauth_settings as oauth_settings

class OAuthLogin(RequestHandler):
    def get(self):
        oauth_client = oauth2.Client2(
            oauth_settings['client_id'],
            oauth_settings['client_secret'],
            oauth_settings['base_url']
        )
        authorization_url = oauth_client.authorization_url(
            redirect_uri=oauth_settings['redirect_url'],
            # params={'scope': 'user'}
        )
        logging.debug('authorization_url: %s' % authorization_url)
        return self.redirect(authorization_url)


class OAuthCallback(RequestHandler):
    def get(self):
        oauth_client = oauth2.Client2(
            oauth_settings['client_id'],
            oauth_settings['client_secret'],
            oauth_settings['base_url']
        )
        code = self.get_argument('code')
        data = oauth_client.access_token(code, oauth_settings['redirect_url'])
        access_token = data.get('access_token')
        logging.debug(access_token)
        (headers, body) = oauth_client.request(
            'https://github.com/api/v2/json/user/show',
            access_token=access_token,
            token_param='access_token'
        )
        logging.debug(headers.get('status'))
        logging.debug(body)
        return body