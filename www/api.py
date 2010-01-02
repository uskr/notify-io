import wsgiref.handlers
import hashlib, time, os

from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.api import urlfetch
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import login_required
from django.utils import simplejson

from models import Account, Notification, Channel
from config import API_HOST, API_VERSION
from app import RequestHandler

class ReplayHandler(RequestHandler):
    def post(self): 
        notice_hash = self.request.path.split('/')[-1]
        notice = Notification.all().filter('hash =', notice_hash).get()
        target = Account.all().filter('api_key =', self.request.get('api_key')).get()
        channel = notice.channel
        if notice and channel.status == 'enabled' and channel.target.key() == target.key():
            self.response.out.write(notice.dispatch())
        else:
            self.error(404)


class NotifyHandler(RequestHandler):
    def post(self): 
        hash = self.request.path.split('/')[-1]
        target = Account.all().filter('hash =', hash).get()
        source = Account.all().filter('api_key =', self.request.get('api_key')).get()
        
        channel = Channel.all().filter('target =', target).filter('source =', source).get()
        approval_notice = None
        if not channel and source and target:
            channel = Channel(target=target, source=source, outlet=target.get_default_outlet())
            channel.put()
            approval_notice = channel.get_approval_notice()
            
        if channel:
            notice = Notification(channel=channel, text=self.request.get('text'), icon=source.source_icon)
            for arg in ['title', 'link', 'icon', 'sticky']:
                value = self.request.get(arg, None)
                if value:
                    setattr(notice, arg, value)
            notice.put()
            channel.count += 1
            channel.put()
            
            if channel.status == 'enabled':
                self.response.out.write(notice.dispatch())
                
            elif channel.status == 'pending':
                self.response.set_status(202)
                if approval_notice:
                    self.response.out.write(":".join([channel.outlet.hash, approval_notice.to_json()]))
                else:
                    self.response.out.write("202 Pending approval")
            elif channel.status == 'disabled':
                self.response.set_status(202)
                self.response.out.write("202 Accepted but disabled")
        else:
            self.error(404)
            self.response.out.write("404 Target or source not found")

def main():
    application = webapp.WSGIApplication([
        ('/api/notify.*', NotifyHandler), 
        ('/api/replay.*', ReplayHandler), 
        ('/api/auth.*', AuthHandler),
        ], debug=True)
    wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
    main()
