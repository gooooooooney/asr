# SSL证书目录

在生产环境中，请将SSL证书文件放置在此目录：

- `cert.pem` - SSL证书文件
- `key.pem` - SSL私钥文件

## 生成自签名证书（仅用于测试）

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout key.pem \
  -out cert.pem \
  -subj "/C=CN/ST=Beijing/L=Beijing/O=ASR API/CN=localhost"
```

## 生产环境

建议使用Let's Encrypt或其他受信任的CA颁发的证书。