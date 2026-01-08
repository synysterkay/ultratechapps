"""
Dev.to and Hashnode publishers
"""
import os
import requests

class DevToPublisher:
    def __init__(self):
        self.api_key = os.getenv('DEVTO_API_KEY')
        if not self.api_key:
            raise ValueError("DEVTO_API_KEY not found in environment variables")
        
        self.base_url = "https://dev.to/api"
        self.headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json"
        }
    
    def publish(self, variant):
        """
        Publish article to Dev.to
        
        Args:
            variant: Blog variant dictionary with title, content, tags
            
        Returns:
            Response dictionary
        """
        try:
            article_data = {
                "article": {
                    "title": variant['title'],
                    "body_markdown": variant['content'],
                    "published": True,
                    "tags": variant.get('tags', [])[:4]  # Max 4 tags
                }
            }
            
            response = requests.post(
                f"{self.base_url}/articles",
                headers=self.headers,
                json=article_data,
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                print(f"✅ Published to Dev.to: {data.get('url')}")
                return {
                    'success': True,
                    'url': data.get('url'),
                    'id': data.get('id')
                }
            else:
                print(f"❌ Dev.to error: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'error': response.text
                }
                
        except Exception as e:
            print(f"❌ Error publishing to Dev.to: {e}")
            return {
                'success': False,
                'error': str(e)
            }


class HashnodePublisher:
    def __init__(self):
        self.api_token = os.getenv('HASHNODE_TOKEN')
        if not self.api_token:
            raise ValueError("HASHNODE_TOKEN not found in environment variables")
        
        self.graphql_url = "https://gql.hashnode.com"
        self.headers = {
            "Authorization": self.api_token,
            "Content-Type": "application/json"
        }
        
        # Get publication ID (you need to set this)
        self.publication_id = os.getenv('HASHNODE_PUBLICATION_ID', '')
    
    def publish(self, variant):
        """
        Publish article to Hashnode
        
        Args:
            variant: Blog variant dictionary with title, content, tags
            
        Returns:
            Response dictionary
        """
        if not self.publication_id:
            print("⚠️ HASHNODE_PUBLICATION_ID not set, skipping Hashnode publish")
            return {'success': False, 'error': 'No publication ID'}
        
        try:
            # Hashnode uses GraphQL
            mutation = """
            mutation PublishPost($input: PublishPostInput!) {
                publishPost(input: $input) {
                    post {
                        id
                        url
                        title
                    }
                }
            }
            """
            
            variables = {
                "input": {
                    "title": variant['title'],
                    "contentMarkdown": variant['content'],
                    "tags": [{"slug": tag.lower().replace(' ', '-')} for tag in variant.get('tags', [])[:6]],
                    "publicationId": self.publication_id
                }
            }
            
            response = requests.post(
                self.graphql_url,
                headers=self.headers,
                json={"query": mutation, "variables": variables},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'errors' in data:
                    print(f"❌ Hashnode error: {data['errors']}")
                    return {
                        'success': False,
                        'error': str(data['errors'])
                    }
                
                post = data.get('data', {}).get('publishPost', {}).get('post', {})
                print(f"✅ Published to Hashnode: {post.get('url')}")
                return {
                    'success': True,
                    'url': post.get('url'),
                    'id': post.get('id')
                }
            else:
                print(f"❌ Hashnode error: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'error': response.text
                }
                
        except Exception as e:
            print(f"❌ Error publishing to Hashnode: {e}")
            return {
                'success': False,
                'error': str(e)
            }
