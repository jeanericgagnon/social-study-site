rule Suspicious_Exec_Strings {
  strings:
    $s1 = "os.system(" nocase
    $s2 = "subprocess.Popen(" nocase
    $s3 = "child_process.exec(" nocase
    $s4 = "curl " nocase
    $s5 = "wget " nocase
    $s6 = "rm -rf" nocase
  condition:
    any of them
}

rule Suspicious_Secret_Exfil_Patterns {
  strings:
    $k1 = /AKIA[0-9A-Z]{16}/
    $k2 = /-----BEGIN (RSA|EC|OPENSSH) PRIVATE KEY-----/
    $k3 = /sk-[A-Za-z0-9]{20,}/
    $k4 = "Authorization: Bearer" nocase
  condition:
    any of them
}
