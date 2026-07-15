"""
生成一个全新的、专属于后端服务的钱包（私钥+地址），不属于任何一个具体的人。

只在本地测试链（Ganache/Hardhat）场景下用——这个私钥不需要去水龙头领币，
本地测试链起链的时候自带的账户已经预充了测试币，随便挑一个测试链打印出来的
账户私钥填进 backend/.env 也可以；这个脚本只是提供另一种方式：自己生成一个
干净的、不跟任何测试链账户列表绑定的地址。

用法：
    python chain/scripts/generate_wallet.py

生成的私钥只会打印在终端，不会自动写入任何文件——请自己复制到 backend/.env 里，
不要把这个私钥发给任何人、不要提交进git。
"""
from eth_account import Account


def main() -> None:
    Account.enable_unaudited_hdwallet_features()
    account = Account.create()

    print("已生成一个新钱包：")
    print(f"  地址（公开，可以分享）：{account.address}")
    print(f"  私钥（保密，不要分享，不要提交进git）：{account.key.hex()}")
    print()
    print("请把私钥这一行加进 backend/.env（本地文件，已被.gitignore排除）：")
    print(f"CHAIN_BACKEND_PRIVATE_KEY={account.key.hex()}")
    print()
    print("如果用的是本地测试链（Ganache/Hardhat），这个新地址默认余额是0，")
    print("需要从本地测试链自带的某个账户转一点测试币过来才能付部署/写入的手续费；")
    print("更简单的做法是：不用这个脚本生成的地址，直接拿本地测试链启动时")
    print("打印出来的账户私钥（自带预充测试币）用，两种方式都可以。")


if __name__ == "__main__":
    main()
