# DarkSpark 服务器备份 | 2026-08-18 (v2 明文版)

## 结构
- content.part-00/01/02 : 明文内容包 (知识库+量化数据+skills+memories+cron+SOUL+state.db+secure脚本)
  - 合并: cat content.part-* > content_plain.tar.gz
  - 解压: tar xzf content_plain.tar.gz -C ~
  - sha256: f4ddfad5d512aad1a5689828dc5bf0496638cf203d2efc269527142e90714622
- secrets_encrypted.enc : 钥匙类 (SSH私钥+.env+config.yaml+交易所凭据) — AES-256加密
  - 解密: openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass pass:'<密码>' -in secrets_encrypted.enc -out secrets.tar.gz
  - 解压: tar xzf secrets.tar.gz -C ~
  - sha256: 41e7dcf7ba5d8d1549aaa517823eb228d719677ebb35fb6b39368681d4843e30
- 密码仅通过 Telegram 发送给本人, 不在仓库内

## 备注
- 明文包不含任何密钥/凭据, 可直接解压使用
- 若密码丢失: 钥匙可重新生成(SSH key/Bot token/API key), 内容包不受影响
