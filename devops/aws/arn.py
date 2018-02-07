"""Utilities for AWS ARN identifiers."""

ARN_CLASS = 'arn'

class ARN(object):
    """Represent and modify ARNs."""

    def __init__(self, string=None, parts=None):
        """Parse an ARN."""
        self.class_ = ARN_CLASS
        if string is not None:
            arn = string.split(':')
            if len(arn) == 7:
                arn[5:] = "{}:{}".format(*arn[5:]),
            if len(arn) != 6:
                message = "ARNs have 6 or 7 components, not {}".format(len(arn))
                raise ValueError(message)
            self.class_, self.partition, self.service, self.region, \
                self.account, self.resource = arn
        elif parts is not None:
            self.class_ = parts['class']
            self.partition = parts['partition']
            self.service = parts['service']
            self.region = parts['region']
            self.account = parts['account']
            self.resource = parts['resource']
        if self.class_ != ARN_CLASS:
            message = "ARN class must be {}, not {}".format(repr(ARN_CLASS),
                                                            repr(self.class_))
            raise ValueError(message)

    def parts(self):
        """Represent ARN as a dict."""
        return {'class': self.class_,
                'partition': self.partition,
                'service': self.service,
                'region': self.region,
                'account': self.account,
                'resource': self.resource}

    def __str__(self):
        """Format ARN."""
        return "{}:{}:{}:{}:{}:{}".format(self.class_, self.partition,
                                          self.service, self.region,
                                          self.account, self.resource)

    def __repr__(self):
        """Code to produce ARN."""
        return "ARN({})".format(repr(str(self)))

def boto_arn(user=None, client=None, sess=None):
    """Get an ARN from a Boto3 user identity, STS client, or session."""
    if user is None:
        if client is None:
            client = sess.client('sts')
        user = client.get_caller_identity()
    return ARN(string=user['Arn'])
