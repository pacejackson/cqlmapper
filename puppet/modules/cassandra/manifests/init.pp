class cassandra {
  include cassandra::java

  file { '/etc/apt/sources.list.d/cassandra.sources.list':
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => 'deb http://debian.datastax.com/community stable main',
  }

  file { '/tmp/cassandra_repo_key':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/cassandra/repo_key',
  }

  exec { 'add cassandra repo key':
    command => 'apt-key add /tmp/cassandra_repo_key',
    unless  => 'apt-key list | grep B999A372',
    before  => Exec['update apt cache'],
    notify  => Exec['update apt cache'],
    require => [
      File['/etc/apt/sources.list.d/cassandra.sources.list'],
      File['/tmp/cassandra_repo_key'],
    ],
  }

  package { 'cassandra':
    ensure  => "2.2.8",
    require => Class['cassandra::java'],
  }

  service { 'cassandra':
    ensure  => running,
    notify => Exec['wait for cassandra service'],
    require => Package['cassandra'],
  }

  exec { 'wait for cassandra service':
    command => 'sleep 10',
    require => Service['cassandra'],
  }
}
