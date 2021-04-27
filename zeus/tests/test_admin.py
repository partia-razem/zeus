

import csv
import datetime
from io import StringIO

from django.test import TestCase, RequestFactory
from django.urls import reverse

from zeus.tests.utils import SetUpAdminAndClientMixin, get_election


def today_plus_days(days):
    return datetime.date.today() + datetime.timedelta(days=days)


class TestHomeView(SetUpAdminAndClientMixin, TestCase):
    def setUp(self):
        super(TestHomeView, self).setUp()

    def login(self):
        self.c.post(self.locations['login'], self.login_data)

    def post_and_get_response(self):
        """
        Create an election and post on admin_home
        to change their official status.
        """
        election = get_election()
        return self.c.post(
            reverse('admin_home'),
            {
                'official': [1],
                'uuid': [election.uuid]
            }
        )

    def test_post_without_login(self):
        """
        If someone tries to do a POST request on admin_home
        without having logged in the view should respond
        with a 403(Permission Denied) HTTP code.
        """
        response = self.c.post(
            reverse('admin_home'),
            {}
        )

        assert response.status_code == 403

    def test_post_without_superadmin(self):
        """
        If someone tries to do a POST request on admin_home
        without having superadmin access the view should
        respond with a 403(Permission Denied) HTTP code.
        """
        self.login()

        response = self.post_and_get_response()

        assert response.status_code == 403

    def test_post_with_superadmin(self):
        """
        If someone tries to do a POST request on admin_home
        with superadmin access the view should
        respond with a 302(Redirection) HTTP code.
        """
        self.admin.superadmin_p = True
        self.admin.save()

        self.login()

        response = self.post_and_get_response()

        assert response.status_code == 302

    def test_get_without_superadmin(self):
        """
        If someone does a GET request on admin_home
        without superadmin access the template
        returned should not contain a form.
        """
        self.login()
        get_election()

        response = self.c.get(
            reverse('admin_home'),
            {}
        )

        assert '<select name="official">' not in response.content.decode()

    def test_get_with_superadmin(self):
        """
        If someone does a GET request on admin_home
        with superadmin access the template
        returned should contain a form.
        """
        self.admin.superadmin_p = True
        self.admin.save()

        self.login()

        # when there are no elections created, we should get a redirect
        response = self.c.get(reverse('admin_home'), {})
        assert response.status_code == 302

        get_election(name='first_election')

        response = self.c.get(
            reverse('admin_home'),
            {}
        )

        assert '</form>' in response.content.decode()
        assert '<select name="official">' in response.content.decode()
        assert '<input type="submit"' in response.content.decode()
        assert '<input type="hidden"' in response.content.decode()

        # ensure the ordering works
        get_election(name='second_election')

        response = self.c.get(reverse('admin_home'), {'order': 'name', 'order_type': 'desc'})
        assert response.context['elections_administered'][0].name == 'second_election'
        assert response.context['elections_administered'][1].name == 'first_election'

        response = self.c.get(reverse('admin_home'), {'order': 'created_at', 'order_type': 'asc'})
        assert response.context['elections_administered'][0].name == 'first_election'
        assert response.context['elections_administered'][1].name == 'second_election'

        # when the order param is invalid, should sort by name, descending
        response = self.c.get(reverse('admin_home'), {'order': 'boom'})
        assert response.context['elections_administered'][0].name == 'second_election'
        assert response.context['elections_administered'][1].name == 'first_election'

        # ensure elections_per_page is handled right
        response = self.c.get(reverse('admin_home'), {'limit': 1})
        assert response.context['elections_per_page'] == 1

        response = self.c.get(reverse('admin_home'), {'limit': '1'})
        assert response.context['elections_per_page'] == 1

        # when limit is invalid, it should fall back to the default
        response = self.c.get(reverse('admin_home'), {'limit': 'boom'})
        assert response.context['elections_per_page'] == 20

    def test_find_elections(self):
        from zeus.views.admin import find_elections

        self.admin.superadmin_p = True
        self.admin.save()
        self.login()

        election_a = get_election(
            name='election A',
            voting_starts_at=today_plus_days(days=1).strftime('%Y-%m-%d'),
            voting_ends_at=today_plus_days(days=2).strftime('%Y-%m-%d')
        )
        election_b = get_election(
            name='election B',
            voting_starts_at=today_plus_days(days=4).strftime('%Y-%m-%d'),
            voting_ends_at=today_plus_days(days=5).strftime('%Y-%m-%d')
        )
        election_c = get_election(
            name='election C',
            trial=True
        )
        for i, e in enumerate([election_a, election_b, election_c]):
            e.completed_at = today_plus_days(days=6+i)
            e.save()

        # in the default case elections should be sorted by created_at, desc
        request = RequestFactory().get(reverse('elections_report_csv'), {})
        request.user = self.admin
        elections = find_elections(request)
        assert len(elections) == 2
        assert elections[0] == election_b
        assert elections[1] == election_a

        request = RequestFactory().get(reverse('elections_report_csv'), {
            'order': 'name',
            'order_type': 'asc',
        })
        request.user = self.admin
        elections = find_elections(request)
        assert len(elections) == 2
        assert elections[0] == election_a
        assert elections[1] == election_b

        request = RequestFactory().get(reverse('elections_report_csv'), {
            'start_date': today_plus_days(days=3).strftime('%d %b %Y'),
        })
        request.user = self.admin
        elections = find_elections(request)
        assert len(elections) == 1
        assert elections[0] == election_b

        request = RequestFactory().get(reverse('elections_report_csv'), {
            'end_date': today_plus_days(days=3).strftime('%d %b %Y'),
        })
        request.user = self.admin
        elections = find_elections(request)
        assert len(elections) == 1
        assert elections[0] == election_a

    def test_elections_report_csv(self):
        self.admin.superadmin_p = True
        self.admin.save()
        self.login()

        election = get_election(
            name='election',
            voting_starts_at=today_plus_days(days=1).strftime('%Y-%m-%d'),
            voting_ends_at=today_plus_days(days=2).strftime('%Y-%m-%d')
        )
        election.completed_at = today_plus_days(days=3)
        election.save()

        response = self.c.get(reverse('elections_report_csv'), {})
        date = datetime.date.today().strftime('%Y-%m-%d')
        # make sure that the headers are right and the response body contains
        # at least one comma
        assert response['Content-Disposition'] == 'attachment; filename=elections_report_%s.csv' % (date)
        assert response.content.decode().find(',') > -1
        lines = [line for line in csv.reader(StringIO(str(response.content.decode())))]
        assert len(lines) == 2
        assert lines[0] == ['Institution', 'Electors', 'Voters', 'Start', 'End', 'uuid', 'Name', 'Polls', 'Administrator', 'Official']

    def test_elections_report(self):
        self.admin.superadmin_p = True
        self.admin.save()
        self.login()

        response = self.c.get(reverse('elections_report'), {})
        assert response.context['elections_count'] == 0
        assert response.context['polls_count'] == 0
        assert response.context['voters_count'] == 0
        assert response.context['voters_voted_count'] == 0
        assert response.context['percentage_voted'] == 0
        assert len(response.context['elections']) == 0

        election = get_election(
            name='election',
            voting_starts_at=today_plus_days(days=1).strftime('%Y-%m-%d'),
            voting_ends_at=today_plus_days(days=2).strftime('%Y-%m-%d')
        )
        election.completed_at = today_plus_days(days=3)
        election.save()

        response = self.c.get(reverse('elections_report'), {})
        assert response.context['elections_count'] == 1
        assert len(response.context['elections']) == 1
