output "nodes" {
  description = "Created node names, roles and IPv4 addresses."
  value = {
    for name, instance in multipass_instance.node : name => {
      role = var.nodes[name].role
      ipv4 = instance.ipv4
    }
  }
}

output "server" {
  description = "Name and IPv4 address of the K3s server node."
  value = one([
    for name, instance in multipass_instance.node : {
      name = name
      ipv4 = instance.ipv4
    } if var.nodes[name].role == "server"
  ])
}
