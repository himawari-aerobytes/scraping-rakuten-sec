# 前提
- ECRリポジトリがアップロードされている。
- Lambda関数が作成されている。
- 環境変数が設定されている。
- 既に画像を保存するバケットが作成済みである。
- LINE Messaging APIがセットアップ済みである。
- 楽天証券アカウントが作成済みである。

# 環境変数
| キー                        | 値                                       |
|-----------------------------|------------------------------------------|
| BUCKET_NAME                 | 画像を保存するS3バケット名               |
| ID                          | 楽天証券のID                             |
| LINE_CHANNEL_ACCESS_TOKEN    | LINE Messaging APIのチャンネルアクセストークン |
| PASS                        | 楽天証券のパスワード                     |
| USER_ID                     | LINEのユーザID（送信先のユーザID）       |

# デプロイ方法
以下のコマンドをecr_deploy.shファイルに貼り付けて実行すると、デプロイが可能です。
```
accountID="アカウントID";
ecrRepoName="ECRのリポジトリ名";
aws ecr get-login-password --region ap-northeast-1 | docker login --username AWS --password-stdin $accountID.dkr.ecr.ap-northeast-1.amazonaws.com
docker build -t $ecrRepoName .
docker tag $ecrRepoName:latest $accountID.dkr.ecr.ap-northeast-1.amazonaws.com/$ecrRepoName:latest
docker push $accountID.dkr.ecr.ap-northeast-1.amazonaws.com/$ecrRepoName:latest

ECR_URI=$accountID.dkr.ecr.ap-northeast-1.amazonaws.com/$ecrRepoName:latest

#lambda更新
aws lambda update-function-code --function-name Lambda関数の名前 --image-uri $ECR_URI
```
