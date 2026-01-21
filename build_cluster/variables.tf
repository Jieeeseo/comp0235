variable img_display_name {
  type = string
  default = "AlmaLinux-9-GenericCloud-9.6-20250522"
}

# your rancher username (e.g. ucbcdwb)
variable username {
  type = string
  default = "zczqh91"
}

variable namespace_ending {
  type = string
  default = "zczqh91-comp0235-ns"
}

# The name of your ssh key uploaded to rancher 
variable keyname {
  type = string
  default = "comp0235-win"
}

variable host {
  type    = number
  default = 1
}

variable worker {
  type    = number
  default = 4
}

variable "host_tags" {
  description = "Tags/labels applied to the host VM "
  type        = map(string)
  default = {
    "condenser_ingress_isEnabled" = "true"
    "condenser_ingress_rabbit_hostname" = "rabbit-zczqh91"
    "condenser_ingress_rabbit_port"     = "15672"
  }
}

