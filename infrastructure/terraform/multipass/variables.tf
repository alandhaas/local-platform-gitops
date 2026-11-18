variable "ubuntu_image" {
  description = "Ubuntu image alias or version used for every Multipass node."
  type        = string
  default     = "24.04"
}

variable "ansible_public_key_path" {
  description = "Public SSH key authorized for Ansible on every node."
  type        = string
  default     = "~/.ssh/id_ed25519.pub"
}

variable "nodes" {
  description = "Multipass machines that will form the K3s cluster."
  type = map(object({
    role   = string
    cpus   = number
    memory = string
    disk   = string
  }))

  default = {
    k3s-server-1 = {
      role   = "server"
      cpus   = 2
      memory = "4GiB"
      disk   = "20GiB"
    }
    k3s-worker-1 = {
      role   = "agent"
      cpus   = 2
      memory = "2GiB"
      disk   = "15GiB"
    }
    k3s-worker-2 = {
      role   = "agent"
      cpus   = 2
      memory = "2GiB"
      disk   = "15GiB"
    }
  }

  validation {
    condition = (
      length([for node in values(var.nodes) : node if node.role == "server"]) == 1 &&
      alltrue([for node in values(var.nodes) : contains(["server", "agent"], node.role)])
    )
    error_message = "nodes must contain exactly one server; every other role must be agent."
  }
}
