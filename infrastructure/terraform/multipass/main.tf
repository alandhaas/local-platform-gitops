locals {
  common_tags = ["k3s", "local-platform"]
}

resource "local_file" "cloud_init" {
  for_each = var.nodes

  filename = "${path.module}/cloud-init/rendered-${each.key}.yaml"
  content = templatefile("${path.module}/cloud-init/node.yaml.tftpl", {
    node_name = each.key
    node_role = each.value.role
    tags      = join(",", local.common_tags)
  })

  file_permission = "0644"
}

resource "multipass_instance" "node" {
  for_each = var.nodes

  name            = each.key
  image           = var.ubuntu_image
  cpus            = each.value.cpus
  memory          = each.value.memory
  disk            = each.value.disk
  cloud_init_file = local_file.cloud_init[each.key].filename
}
