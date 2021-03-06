#!/usr/bin/env python
import logging
import sys
import tornado.ioloop
import tornado.web
import tornado.httputil
import tornado.escape
import yaml
import psutil
import docker
import settings_slave




logging.basicConfig(filename=settings_slave.log, level=30,
                    format=u'%(filename)s[LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s', )
ch = logging.StreamHandler(sys.stdout)
docker_client = docker.Client(base_url=settings_slave.docker_url)


class DockerWatcherSlave:
    class InfoHandler(tornado.web.RequestHandler):

        def return_mb(self, value):
            return int(value / float(2 ** 20))

        def return_gb(self, value):
            #return int(value / float(2 ** 30))
            return int(value / float(1000000000))
        def get(self):
            logging.warning('/info')
            info_dict = {}
            info_dict['total_cpus'] = psutil.cpu_count()
            info_dict['total_memory'] = self.return_gb(psutil.virtual_memory().total)
            info_dict['total_disk'] = self.return_gb(psutil.disk_usage('/').total)
            info_dict['total_network'] = psutil.net_if_stats()['eth0'].speed
            self.write(yaml.dump(info_dict))
            self.set_status(200)

    class StopHandler(tornado.web.RequestHandler):
        def get(self):
            logging.warning('/stop')
            self.write('stopping slave\n')
            self.set_status(200)
            tornado.ioloop.IOLoop.instance().stop()

    class RunHandler(tornado.web.RequestHandler):
        def post(self):
            logging.warning('/run_pod')
            data = yaml.safe_load(self.request.body)
            image = data['image']
            command = data['command']
            pod_name = data['name']
            memory = data['memory']
            slave_images = []
            images_data = docker_client.images()
            for i in images_data:
                for j in i['RepoTags']:
                    slave_images.append(j)
            if not image in slave_images:
                logging.warning('pull ' + image)
                docker_client.pull(image)
            logging.warning('create_container')
            self.container = docker_client.create_container(
                image=image, command=command)
            container_id = self.container.get('Id')
            logging.warning('start_container')
            start_response = docker_client \
                .start(container=container_id)
            self.write(container_id)
            logging.warning('running pod ' + pod_name + ' id: ' + self.container.get('Id'))
            self.set_status(200)

    class KillHandler(tornado.web.RequestHandler):
        def get(self):
            logging.warning('/kill')
            container_id = self.request.body
            kill_response = docker_client.kill(
                container=container_id)
            self.write(kill_response)
            self.set_status(200)

    class GetContainersHandler(tornado.web.RequestHandler):
        def get(self):
            logging.info('/get_containers')
            containers_list = docker_client.containers()
            #logging.warning(containers_list)
            response = str(yaml.safe_dump(containers_list))
            self.write(response)
            self.set_status(200)

    def run(self):
        self.tornadoapp = tornado.web.Application([
            (r'/info', DockerWatcherSlave.InfoHandler),
            (r'/stop', DockerWatcherSlave.StopHandler),
            (r'/run_pod', DockerWatcherSlave.RunHandler),
            (r'/kill', DockerWatcherSlave.KillHandler),
            (r'/get_containers', DockerWatcherSlave.GetContainersHandler)
        ])
        self.tornadoapp.listen(settings_slave.listen_port,
                               settings_slave.listen_host)
        tornado.ioloop.IOLoop.instance().start()


if __name__ == '__main__':
    try:
        logging.warning('starting slave')
        docker_watcher = DockerWatcherSlave()
        docker_watcher.run()
    except Exception, e:
        logging.error(e, exc_info=True)
        exit(1)
