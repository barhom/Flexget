from __future__ import unicode_literals, division, absolute_import
from urlparse import urlparse
import logging
from flexget import plugin
from flexget.event import event
from flexget.entry import Entry
from flexget.utils import qualities
from requests import RequestException

log = logging.getLogger('couchpotato')


class CouchPotato(object):
    schema = {
        'type': 'object',
        'properties': {
            'base_url': {'type': 'string'},
            'port': {'type': 'number', 'default': 80},
            'api_key': {'type': 'string'},
            'include_data': {'type': 'boolean', 'default': False}
        },
        'required': ['api_key', 'base_url'],
        'additionalProperties': False
    }

    def quality_requirement_builder(self, quality_profile):
        """
        Converts CP's quality profile to a format that can be converted to FlexGet QualityRequirement
        """
        # TODO: Not all values have exact matches in flexget, need to update flexget qualities
        sources = {'BR-Disk': 'remux',  # Not a perfect match, but as close as currently possible
                   'brrip': 'bluray',
                   'dvdr': 'dvdrip',  # Not a perfect match, but as close as currently possible
                   'dvdrip': 'dvdrip',
                   'scr': 'dvdscr',
                   'r5': 'r5',
                   'tc': 'tc',
                   'ts': 'ts',
                   'cam': 'cam'}

        resolutions = {'1080p': '1080p',
                       '720p': '720p'}

        # Separate strings are needed for each QualityComponent
        # TODO list is converted to set because if a quality has 3d type in CP, it gets duplicated during the conversion
        # TODO when (and if) 3d is supported in flexget this will be needed to removed
        res_string = '|'.join(
            set([resolutions[quality] for quality in quality_profile['qualities'] if quality in resolutions]))
        source_string = '|'.join(
            set([sources[quality] for quality in quality_profile['qualities'] if quality in sources]))

        return res_string + ' ' + source_string

    def on_task_input(self, task, config):
        """Creates an entry for each item in your couchpotato wanted list.

        Syntax:

        couchpotato:
          base_url: <value>
          port: <value> (Default is 80)
          api_key: <value>
          include_data: <value> (Boolean, default is False.

        Options base_url and api_key are required.
        When the include_data property is set to true, the
        """

        parsedurl = urlparse(config.get('base_url'))
        url = '{}://{}:{}{}/api/{}/movie.list?status=active'.format(parsedurl.scheme, parsedurl.netloc,
                                                                    config.get('port'), parsedurl.path,
                                                                    config.get('api_key'))
        try:
            json = task.requests.get(url).json()
        except RequestException:
            raise plugin.PluginError(
                'Unable to connect to Couchpotato at {}://{}:{}{}.'.format(parsedurl.scheme, parsedurl.netloc,
                                                                           config.get('port'), parsedurl.path))

        # Gets profile and quality lists if include_data is TRUE
        if config.get('include_data'):
            profile_url = '{}://{}:{}{}/api/{}/profile.list'.format(parsedurl.scheme, parsedurl.netloc,
                                                                    config.get('port'), parsedurl.path,
                                                                    config.get('api_key'))
            try:
                profile_json = task.requests.get(profile_url).json()
            except RequestException as e:
                raise plugin.PluginError(
                    'Unable to connect to Couchpotato at {}://{}:{}{}. Error: {}'.format(parsedurl.scheme,
                                                                                         parsedurl.netloc,
                                                                                         config.get('port'),
                                                                                         parsedurl.path, e))
        entries = []
        for movie in json['movies']:
            quality_req = ''
            if movie['status'] == 'active':
                if config.get('include_data'):
                    for profile in profile_json['list']:
                        if profile['_id'] == movie['profile_id']:  # Matches movie profile with profile JSON
                            quality_req = self.quality_requirement_builder(profile)
                title = movie["title"]
                imdb = movie['info'].get('imdb')
                tmdb = movie['info'].get('tmdb_id')
                entry = Entry(title=title,
                              url='',
                              imdb_id=imdb,
                              tmdb_id=tmdb,
                              quality_req=quality_req)
                if entry.isvalid():
                    entries.append(entry)
                else:
                    log.error('Invalid entry created? {}' % entry)
                    continue
                # Test mode logging
                if entry and task.options.test:
                    log.info("Test mode. Entry includes:")
                    log.info("    Title: {}".format(entry["title"]))
                    log.info("    URL: {}".format(entry["url"]))
                    log.info("    IMDB ID: {}".format(entry["imdb_id"]))
                    log.info("    TMDB ID: {}".format(entry["tmdb_id"]))
                    log.info("    Quality: {}".format(entry["quality_req"]))

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(CouchPotato, 'couchpotato', api_ver=2)
