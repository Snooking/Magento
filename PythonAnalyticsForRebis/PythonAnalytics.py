from apiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import pairwise_distances
from sklearn.preprocessing import normalize
import csv

SCOPES = ['https://www.googleapis.com/auth/analytics.readonly']
KEY_FILE_LOCATION = './client_id.json'
VIEW_ID = 'ga:185501303'

def initialize_analyticsreporting():
  """Initializes an Analytics Reporting API V4 service object.
  Returns: An authorized Analytics Reporting API V4 service object.
  """  
  credentials = ServiceAccountCredentials.from_json_keyfile_name(
      KEY_FILE_LOCATION, SCOPES)

  # Build the service object.
  analytics = build('analyticsreporting', 'v4', credentials=credentials)

  return analytics
  

def get_report(analytics, start_date, end_date = 'today'):
  """Queries the Analytics Reporting API V4.
  Args: 
	analytics: An authorized Analytics Reporting API V4 service object.
  Returns: The Analytics Reporting API V4 response.
  """
  return analytics.reports().batchGet(
      body={
        'reportRequests': [
        {
          'viewId': VIEW_ID,
          'dateRanges': [{'startDate': start_date, 'endDate': end_date}],
          'metrics': [{'expression': 'ga:userTimingValue'}],
          'dimensions': [ {'name': 'ga:userTimingVariable'}]
        }]
      }
  ).execute()

def save_response(response, users_path, items_path, ratings_path):
  """ Creater three tables for users, items and ratings, from ga api response
  Args:	
		response: An Analytics Reporting API V4 Response of user Timing
		user_path: output file name for users
		item_path: output file name for items
		ratings_path: output file name for user-item ratings
  """
  ratings_file = open(ratings_path, 'w')
  users_file = open(users_path, 'w')
  items_file = open(items_path, 'w')
  

  for report in response.get('reports', []):
    columnHeader = report.get('columnHeader', {})
    dimensionHeaders = columnHeader.get('dimensions', [])
    metricHeaders = columnHeader.get('metricHeader', {}).get('metricHeaderEntries', [])

    users_ids = []

    for row in report.get('data', {}).get('rows', []):
      dimensions = row.get('dimensions', [])
      dateRangeValues = row.get('metrics', [])

      for header, dimension in zip(dimensionHeaders, dimensions):
        # odrzucenie jesli niepasujacy
        if not dimension.startswith('Product_id'):
         continue

        # Wyciaganiecie product id i user email z dimension
        id_and_email = dimension.split(' ');
        email = id_and_email[1][15:len(id_and_email[1])]
        id = id_and_email[0][11:len(id_and_email[0])]

        if email == 'undefined' or not id.isdigit():
          continue

        value = dateRangeValues[0].get('values')[0] 

		# If user has an id
        if users_ids.count(email) == 0:
          user_id = len(users_ids)
          users_ids.append(email)
          users_file.write(str(user_id) + ',' + email + '\n')
        else:
          user_id = users_ids.index(email)

        items_file.write(id + '\n')
        ratings_file.write(str(user_id) + ',' + id + ',' + value + '\n')


  ratings_file.close()
  users_file.close()
  items_file.close()


def create_predictions(ratings_path):
  """ Creates user based and item based predicitons based on collaborative filtering method
    Args:	
		ratings_path: output file name for user-item ratings
	Returns:
		user based predictions list
		item based prediciotns list
  """ 
  r_cols = ['user_id', 'item_id', 'rating']
  ratings = pd.read_csv(ratings_path, sep=',', names=r_cols,encoding='latin-1')
  
  print(ratings.sort_values('user_id'))  
  
  # Number of unique users and items
  n_users = ratings.user_id.unique().shape[0]
  n_items = max(ratings.item_id)

  # Build user-item matrix
  
  data_matrix = np.zeros((n_users, n_items))
  for line in ratings.itertuples():
    data_matrix[line[1], line[2] - 1] = line[3]
	
	
  print(data_matrix[2])
  data_matrix = normalize(data_matrix)
  print(data_matrix[2])

  # Calculate user and item similarities
  user_similarity = pairwise_distances(data_matrix, metric = 'cosine')
  item_similarity = pairwise_distances(data_matrix.T, metric = 'cosine')

  # Calculate predictions
  user_prediction = predict(data_matrix, user_similarity, type = 'user')
  item_prediction = predict(data_matrix, item_similarity, type='item')

  return user_prediction.tolist(), item_prediction.tolist()


def predict(ratings, similarity, type = 'user'):
  if type == 'user':
    mean_user_rating = ratings.mean(axis = 1)
    ratings_diff = (ratings - mean_user_rating[:, np.newaxis])
    pred = mean_user_rating[:, np.newaxis] + similarity.dot(ratings_diff) / np.array([np.abs(similarity).sum(axis=1)]).T
  elif type == 'item':
    pred = ratings.dot(similarity) / np.array([np.abs(similarity).sum(axis=1)])
  return pred


def best_predictions(prediction, k = 5):
	
  best_predictions = []

  for row in prediction:
    row_best_predictions = []
    for i in range(0, k):
      item_id = row.index(max(row))
      row[item_id] = min(row)
      row_best_predictions.append(item_id)
    best_predictions.append(row_best_predictions)

  return best_predictions

def most_popular_products(ratings_path, k = 10):
  r_cols = ['user_id', 'item_id', 'rating']
  ratings = pd.read_csv(ratings_path, sep=',', names=r_cols,encoding='utf-8')
 
  sum_by_items = ratings.groupby('item_id', as_index=False).agg('sum')

  k_largest_ratings = sum_by_items.nlargest(k, 'rating')

  return k_largest_ratings['item_id'].tolist()	

  
def save_most_popular(most_popular_path, most_popular_array): 
  with open(most_popular_path, 'w') as output:
    output.write(''.join(str(i) + ' ' for i in most_popular_array)) 

def save_predictions(predictions, output_path, users_path):

  with open(output_path, 'w') as output, open(users_path, 'r') as users_file:
    reader = csv.reader(users_file)
    users = list(reader)
    users_id_counter = 0

    for row in predictions:
      output.write(users[users_id_counter][1] + ': ' + ''.join(str(e) + ' ' for e in row) + '\n')
      users_id_counter = users_id_counter + 1


def main():
  start_date = '2019-01-12'

  users_path = 'output/users.data'
  items_path = 'output/items.data'
  ratings_path = 'output/ratings.data'

  user_based_predictions_path = 'output/user_based_predictions.txt'
  item_based_predictions_path = 'output/item_based_predictions.txt'
  most_popular_products_path = 'output/most_popular.txt'

  analytics = initialize_analyticsreporting()
  response = get_report(analytics, start_date)
   
  
  save_response(response, users_path, items_path, ratings_path)
  
  

  user_based_predictions, item_based_predictions = create_predictions(ratings_path)

  best_user_predictions = best_predictions(user_based_predictions)
  best_item_predictions = best_predictions(item_based_predictions)
  
  most_popular_products_array = most_popular_products(ratings_path)
  
  save_predictions(best_user_predictions, user_based_predictions_path, users_path)
  save_predictions(best_item_predictions, item_based_predictions_path, users_path)
  save_most_popular(most_popular_products_path, most_popular_products_array)

if __name__ == '__main__':
  main()