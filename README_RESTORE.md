# DarkSpark 重要数据备份恢复说明
日期: 2026-08-18
加密: AES-256-CBC + PBKDF2 200000次迭代
校验: sha256 ea4b0637d3aa6144903c76e0fe3f4bb947a85be4041e72f0038c8af79d41bd8c

## 恢复步骤
1. 下载全部 .enc 分卷到同一目录
2. 合并: cat core.part-*.enc > 合并后按顺序
3. 解密: openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass pass:'<密码>' -in core.part-00.enc -out core.part-00
4. 合并还原: cat core.part-00 core.part-01 > core_important.tar.gz
5. 解包: tar xzf core_important.tar.gz -C ~
6. 校验: sha256sum core_important.tar.gz 应等于上面值
