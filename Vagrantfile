# -*- mode: ruby -*-
# vi: set ft=ruby :

=begin

DOCUMENTATION
=============

This vagrant instance installs all the various versions of python needed to run the tests and installs redis-server cluster.

do:

```
vagrant up
vagrant ssh
```

once inside the vagrant instance you should be able to do:
```
cd /vagrant
make test
```

This will put you in this current directory and run the tests inside of vagrant.

=end

VAGRANTFILE_API_VERSION = "2"

$script = <<SCRIPT
set -ex
echo "" | sudo add-apt-repository ppa:fkrull/deadsnakes
sudo apt-get update
sudo apt-get install -y git curl python-dev python-pip python3.2-dev python3.3-dev make build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm
sudo pip install pep8 tox hiredis pyopenssl coverage
cd /vagrant && sudo make redis-install
curl -L -s https://raw.githubusercontent.com/yyuu/pyenv-installer/master/bin/pyenv-installer | bash
export PATH="$HOME/.pyenv/bin:$PATH"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"
pyenv install 3.4.1
pyenv shell 3.4.1

cat >> "$HOME/.bashrc" <<'EOF'
export PATH="$HOME/.pyenv/bin:$PATH"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"
EOF

SCRIPT


Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
  config.vm.box = "redis-py-cluster"
  config.vm.box_url = "https://cloud-images.ubuntu.com/vagrant/trusty/current/trusty-server-cloudimg-amd64-vagrant-disk1.box"
  config.vm.provision "shell", inline: $script, :privileged => false
end
